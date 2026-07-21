"""Synchronize the local SQLite Agent repository into Qdrant."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from intent_hub.agent_compare import normalize_corpus
from intent_hub.config import Config


def agent_hash(agent) -> str:
    payload = {
        "id": agent.id,
        "title": agent.title,
        "utterances": normalize_corpus(agent.utterances),
        "negative_samples": normalize_corpus(agent.negative_samples),
        "score_threshold": agent.score_threshold,
        "negative_threshold": agent.negative_threshold,
    }
    return hashlib.md5(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


class SyncService:
    def __init__(self, component_manager, source=None, state_path=None):
        self.components = component_manager
        # Only retained for compatibility with older direct unit callers. HTTP sync never supplies it.
        self.source = source
        self.state_path = Path(state_path or Config.SYNC_STATE_FILE)

    def sync(self, mode: str = "incremental", agent_ids: list[int] | None = None) -> dict:
        if mode not in {"incremental", "full"}:
            raise ValueError("mode 仅支持 incremental 或 full")
        connection = self._open_state()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                raise RuntimeError("已有向量同步任务正在运行") from error
            self._legacy_pull_if_requested(connection)
            agents = self._active_agents(agent_ids)
            result = self._full_sync(connection, agents) if mode == "full" else self._incremental_sync(connection, agents, agent_ids)
            connection.commit()
            self._set_store_metadata("last_vector_sync_at", datetime.now(timezone.utc).isoformat())
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _legacy_pull_if_requested(self, connection) -> None:
        if self.source is None:
            return
        existing = {agent.id: agent for agent in self.components.agent_store.all()}
        incoming = self.source.fetch_all()
        if not incoming:
            self._legacy_empty = True
            return
        previous = set(existing) | set(self._load_hashes(connection, Config.QDRANT_COLLECTION))
        deleted = previous - {agent.id for agent in incoming}
        self._guard_deletions(len(previous), len(deleted))
        for agent in incoming:
            if agent.id in existing:
                agent.score_threshold = existing[agent.id].score_threshold
                agent.negative_threshold = existing[agent.id].negative_threshold
        self.components.agent_store.replace(incoming)

    def _active_agents(self, agent_ids=None):
        store = self.components.agent_store
        agents = store.active() if hasattr(store, "active") else store.all()
        agents = [agent for agent in agents if getattr(agent, "lifecycle_status", "active") == "active"]
        if agent_ids is not None:
            selected = set(agent_ids)
            agents = [agent for agent in agents if agent.id in selected]
        return agents

    def _incremental_sync(self, connection, agents, agent_ids=None) -> dict:
        if getattr(self, "_legacy_empty", False):
            result = self._empty_result("incremental")
            result["warning"] = "上游没有包含指定标签的 Agent，已保留现有索引"
            return result
        collection = Config.QDRANT_COLLECTION
        saved_hashes = self._load_hashes(connection, collection)
        current_hashes = {agent.id: agent_hash(agent) for agent in agents}
        if agent_ids is None:
            deleted_ids = set(saved_hashes) - set(current_hashes)
            self._guard_deletions(len(saved_hashes), len(deleted_ids))
        else:
            selected = set(agent_ids)
            deleted_ids = {agent_id for agent_id in selected if agent_id in saved_hashes and agent_id not in current_hashes}
        changed = [agent for agent in agents if saved_hashes.get(agent.id) != current_hashes[agent.id]]
        qdrant = self.components.qdrant_client
        # Route-level replacement guarantees removed and renamed corpus points cannot remain stale.
        qdrant.delete_routes({agent.id for agent in changed} | deleted_ids)
        self._upsert_agents(qdrant, changed)

        merged_hashes = dict(saved_hashes)
        for agent_id in deleted_ids:
            merged_hashes.pop(agent_id, None)
        merged_hashes.update({agent.id: current_hashes[agent.id] for agent in changed})
        if agent_ids is None:
            self._validate(qdrant, agents)
            merged_hashes = current_hashes
        self._replace_hashes(connection, collection, merged_hashes)
        return self._result("incremental", agents, len(changed), len(deleted_ids))

    def _full_sync(self, connection, agents) -> dict:
        if not agents:
            return self._empty_result("full")
        configured = Config.QDRANT_COLLECTION
        alias = configured if configured.endswith("__active") else f"{configured}__active"
        base = alias.removesuffix("__active")
        generation = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        target_name = f"{base}__{generation}"
        target = self.components.create_qdrant(target_name)
        self._upsert_agents(target, agents)
        self._validate(target, agents)
        target.switch_alias(alias)
        if configured != alias:
            Config.save_collection(alias)
            self.components.reset_qdrant()
        self._replace_hashes(connection, alias, {agent.id: agent_hash(agent) for agent in agents})
        result = self._result("full", agents, len(agents), 0)
        result.update({"collection": alias, "physical_collection": target_name})
        return result

    def _encode_routes(self, agents):
        routes = []
        for agent in agents:
            if not agent.utterances:
                continue
            routes.append({
                "route_id": agent.id, "route_name": agent.title,
                "utterances": agent.utterances,
                "positive_embeddings": self.components.encoder.encode(agent.utterances),
                "negative_samples": agent.negative_samples,
                "negative_embeddings": self.components.encoder.encode(agent.negative_samples),
                "score_threshold": agent.score_threshold,
                "negative_threshold": agent.negative_threshold,
                "route_hash": agent_hash(agent), "model_name": Config.EMBEDDING_MODEL_NAME,
            })
        return routes

    def _upsert_agents(self, qdrant, agents) -> None:
        for start in range(0, len(agents), Config.QDRANT_WRITE_BATCH_SIZE):
            routes = self._encode_routes(agents[start:start + Config.QDRANT_WRITE_BATCH_SIZE])
            if routes:
                qdrant.upsert_routes(routes, batch_size=Config.QDRANT_WRITE_BATCH_SIZE)

    @staticmethod
    def _guard_deletions(previous_count, deleted_count):
        if previous_count and deleted_count / previous_count > Config.MAX_DELETE_RATIO:
            raise ValueError(f"本次将删除 {deleted_count}/{previous_count} 个 Agent，超过安全阈值；请确认后使用 full 模式")

    @staticmethod
    def _validate(qdrant, agents):
        indexed = [agent for agent in agents if agent.utterances]
        expected_hashes = {agent.id: agent_hash(agent) for agent in indexed}
        expected_points = sum(len(agent.utterances) + len(agent.negative_samples) for agent in indexed)
        actual = qdrant.index_summary()
        if actual["points_count"] != expected_points or actual["route_ids"] != sorted(expected_hashes) or actual["route_hashes"] != expected_hashes:
            raise RuntimeError(f"Qdrant 校验失败：期望 {expected_points} points，实际 {actual['points_count']}")

    def _open_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.state_path, timeout=0)
        connection.execute("CREATE TABLE IF NOT EXISTS sync_state (collection TEXT NOT NULL, agent_id INTEGER NOT NULL, source_hash TEXT NOT NULL, PRIMARY KEY (collection, agent_id))")
        connection.commit()
        return connection

    @staticmethod
    def _load_hashes(connection, collection):
        return dict(connection.execute("SELECT agent_id, source_hash FROM sync_state WHERE collection = ?", (collection,)))

    @staticmethod
    def _replace_hashes(connection, collection, hashes):
        connection.execute("DELETE FROM sync_state WHERE collection = ?", (collection,))
        connection.executemany("INSERT INTO sync_state (collection, agent_id, source_hash) VALUES (?, ?, ?)", ((collection, key, value) for key, value in hashes.items()))

    @staticmethod
    def _result(mode, agents, changed_agents, deleted_agents):
        indexed = [agent for agent in agents if agent.utterances]
        return {"mode": mode, "agents_count": len(agents), "indexed_agents_count": len(indexed), "changed_agents": changed_agents, "deleted_agents": deleted_agents, "unchanged_agents": len(agents) - changed_agents, "positive_points": sum(len(a.utterances) for a in indexed), "negative_points": sum(len(a.negative_samples) for a in indexed)}

    @staticmethod
    def _empty_result(mode):
        return {"mode": mode, "agents_count": 0, "indexed_agents_count": 0, "changed_agents": 0, "deleted_agents": 0, "unchanged_agents": 0, "positive_points": 0, "negative_points": 0, "warning": "本地没有可同步的 Agent，已保留现有索引"}

    def _set_store_metadata(self, key, value):
        if hasattr(self.components.agent_store, "set_metadata"):
            self.components.agent_store.set_metadata(key, value)

    def status(self) -> dict:
        all_agents = self.components.agent_store.all()
        active = self._active_agents()
        hashes = {agent.id: agent_hash(agent) for agent in active if agent.utterances}
        expected_points = sum(len(agent.utterances) + len(agent.negative_samples) for agent in active if agent.utterances)
        actual = self.components.qdrant_client.index_summary()
        synced = actual["points_count"] == expected_points and actual["route_ids"] == sorted(hashes) and actual["route_hashes"] == hashes
        connection = self._open_state()
        try:
            saved = self._load_hashes(connection, Config.QDRANT_COLLECTION)
        finally:
            connection.close()
        dirty = len(set(saved) ^ set(hashes)) + sum(saved.get(key) != value for key, value in hashes.items())
        store = self.components.agent_store
        return {
            "agents_count": len(all_agents), "active_agents_count": len(active),
            "pending_changes": dirty, "collection": Config.QDRANT_COLLECTION,
            "expected_points": expected_points, "points_count": actual["points_count"], "synced": synced,
            "last_pull_at": store.get_metadata("last_pull_at") if hasattr(store, "get_metadata") else None,
            "last_vector_sync_at": store.get_metadata("last_vector_sync_at") if hasattr(store, "get_metadata") else None,
        }
