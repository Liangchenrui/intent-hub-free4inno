"""Synchronize upstream Agents into Qdrant."""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from intent_hub.agent_source import AgentSource
from intent_hub.config import Config


def agent_hash(agent) -> str:
    return hashlib.md5(
        json.dumps(agent.model_dump(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


class SyncService:
    def __init__(self, component_manager, source=None, state_path=None):
        self.components = component_manager
        self.source = source or AgentSource()
        self.state_path = Path(state_path or Config.SYNC_STATE_FILE)

    def sync(self, mode: str = "incremental") -> dict:
        if mode not in {"incremental", "full"}:
            raise ValueError("mode 仅支持 incremental 或 full")
        connection = self._open_state()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                raise RuntimeError("已有同步任务正在运行") from error
            result = (
                self._full_sync(connection)
                if mode == "full"
                else self._incremental_sync(connection)
            )
            connection.commit()
            return result
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _incremental_sync(self, connection) -> dict:
        existing = {agent.id: agent for agent in self.components.agent_store.all()}
        agents = self._fetch_agents(existing)
        if not agents:
            return self._empty_result("incremental")

        collection = Config.QDRANT_COLLECTION
        saved_hashes = self._load_hashes(connection, collection)
        current_hashes = {agent.id: agent_hash(agent) for agent in agents}
        previous_ids = set(existing) | set(saved_hashes)
        current_ids = set(current_hashes)
        deleted_ids = previous_ids - current_ids
        self._guard_deletions(len(previous_ids), len(deleted_ids))

        changed = [
            agent for agent in agents if saved_hashes.get(agent.id) != current_hashes[agent.id]
        ]
        qdrant = self.components.qdrant_client

        # A missing local snapshot is an exceptional recovery path; clear that route before rewriting it.
        qdrant.delete_routes(
            {agent.id for agent in changed if agent.id in saved_hashes and agent.id not in existing}
        )
        self._upsert_agents(qdrant, changed)

        stale_point_ids = set()
        for agent in changed:
            previous = existing.get(agent.id)
            if previous is None:
                continue
            desired = qdrant.point_ids(
                agent.id, agent.title, agent.utterances, agent.negative_samples
            )
            stale_point_ids.update(
                qdrant.point_ids(
                    previous.id,
                    previous.title,
                    previous.utterances,
                    previous.negative_samples,
                )
                - desired
            )
            stale_point_ids.update(
                qdrant.point_ids(
                    previous.id,
                    previous.title,
                    previous.utterances,
                    previous.negative_samples,
                    legacy=True,
                )
                - desired
            )
        qdrant.delete_points(stale_point_ids)
        qdrant.delete_routes(deleted_ids)

        self._validate(qdrant, agents)
        self.components.agent_store.replace(agents)
        self._replace_hashes(connection, collection, current_hashes)
        return self._result(
            "incremental",
            agents,
            changed_agents=len(changed),
            deleted_agents=len(deleted_ids),
        )

    def _full_sync(self, connection) -> dict:
        existing = {agent.id: agent for agent in self.components.agent_store.all()}
        agents = self._fetch_agents(existing)
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
        # ponytail: retain old physical collections for rollback; cleanup needs an explicit policy.

        if configured != alias:
            Config.save_collection(alias)
            self.components.reset_qdrant()
        self.components.agent_store.replace(agents)
        self._replace_hashes(connection, alias, {agent.id: agent_hash(agent) for agent in agents})
        result = self._result("full", agents, changed_agents=len(agents), deleted_agents=0)
        result.update({"collection": alias, "physical_collection": target_name})
        return result

    def _fetch_agents(self, existing: dict) -> list:
        agents = self.source.fetch_all()
        for agent in agents:
            if agent.id in existing:
                agent.score_threshold = existing[agent.id].score_threshold
                agent.negative_threshold = existing[agent.id].negative_threshold
        return agents

    def _encode_routes(self, agents: list) -> list[dict]:
        routes = []
        for agent in agents:
            if not agent.utterances:
                continue
            routes.append(
                {
                    "route_id": agent.id,
                    "route_name": agent.title,
                    "utterances": agent.utterances,
                    "positive_embeddings": self.components.encoder.encode(agent.utterances),
                    "negative_samples": agent.negative_samples,
                    "negative_embeddings": self.components.encoder.encode(agent.negative_samples),
                    "score_threshold": agent.score_threshold,
                    "negative_threshold": agent.negative_threshold,
                    "route_hash": agent_hash(agent),
                    "model_name": Config.EMBEDDING_MODEL_NAME,
                }
            )
        return routes

    def _upsert_agents(self, qdrant, agents: list) -> None:
        for start in range(0, len(agents), Config.QDRANT_WRITE_BATCH_SIZE):
            routes = self._encode_routes(agents[start : start + Config.QDRANT_WRITE_BATCH_SIZE])
            if routes:
                qdrant.upsert_routes(routes, batch_size=Config.QDRANT_WRITE_BATCH_SIZE)

    @staticmethod
    def _guard_deletions(previous_count: int, deleted_count: int) -> None:
        if previous_count and deleted_count / previous_count > Config.MAX_DELETE_RATIO:
            raise ValueError(
                f"本次将删除 {deleted_count}/{previous_count} 个 Agent，超过安全阈值；请确认后使用 full 模式"
            )

    @staticmethod
    def _validate(qdrant, agents: list) -> None:
        indexed = [agent for agent in agents if agent.utterances]
        expected_hashes = {agent.id: agent_hash(agent) for agent in indexed}
        expected_points = sum(
            len(agent.utterances) + len(agent.negative_samples) for agent in indexed
        )
        actual = qdrant.index_summary()
        if (
            actual["points_count"] != expected_points
            or actual["route_ids"] != sorted(expected_hashes)
            or actual["route_hashes"] != expected_hashes
        ):
            raise RuntimeError(
                f"Qdrant 校验失败：期望 {expected_points} points，实际 {actual['points_count']}"
            )

    def _open_state(self):
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.state_path, timeout=0)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS sync_state (
                collection TEXT NOT NULL,
                agent_id INTEGER NOT NULL,
                source_hash TEXT NOT NULL,
                PRIMARY KEY (collection, agent_id)
            )
            """
        )
        connection.commit()
        return connection

    @staticmethod
    def _load_hashes(connection, collection: str) -> dict[int, str]:
        return dict(
            connection.execute(
                "SELECT agent_id, source_hash FROM sync_state WHERE collection = ?",
                (collection,),
            )
        )

    @staticmethod
    def _replace_hashes(connection, collection: str, hashes: dict[int, str]) -> None:
        connection.execute("DELETE FROM sync_state WHERE collection = ?", (collection,))
        connection.executemany(
            "INSERT INTO sync_state (collection, agent_id, source_hash) VALUES (?, ?, ?)",
            ((collection, agent_id, value) for agent_id, value in hashes.items()),
        )

    @staticmethod
    def _result(mode: str, agents: list, changed_agents: int, deleted_agents: int) -> dict:
        indexed = [agent for agent in agents if agent.utterances]
        return {
            "mode": mode,
            "agents_count": len(agents),
            "indexed_agents_count": len(indexed),
            "changed_agents": changed_agents,
            "deleted_agents": deleted_agents,
            "unchanged_agents": len(agents) - changed_agents,
            "positive_points": sum(len(agent.utterances) for agent in indexed),
            "negative_points": sum(len(agent.negative_samples) for agent in indexed),
        }

    @staticmethod
    def _empty_result(mode: str) -> dict:
        return {
            "mode": mode,
            "agents_count": 0,
            "indexed_agents_count": 0,
            "changed_agents": 0,
            "deleted_agents": 0,
            "unchanged_agents": 0,
            "positive_points": 0,
            "negative_points": 0,
            "warning": "上游没有包含指定标签的 Agent，已保留现有索引",
        }

    def update_thresholds(self, agent_id: int, score_threshold: float, negative_threshold: float):
        connection = self._open_state()
        try:
            try:
                connection.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as error:
                raise RuntimeError("同步任务正在运行，暂时不能更新阈值") from error
            current = self.components.agent_store.get(agent_id)
            if current is None:
                raise ValueError("Agent 不存在")
            updated = current.model_copy(
                update={
                    "score_threshold": score_threshold,
                    "negative_threshold": negative_threshold,
                }
            )
            self.components.qdrant_client.update_route_thresholds(
                route_id=agent_id,
                score_threshold=score_threshold,
                negative_threshold=negative_threshold,
                route_hash=agent_hash(updated),
            )
            agents = [
                updated if agent.id == agent_id else agent
                for agent in self.components.agent_store.all()
            ]
            self.components.agent_store.replace(agents)
            connection.execute(
                """
                INSERT INTO sync_state (collection, agent_id, source_hash) VALUES (?, ?, ?)
                ON CONFLICT(collection, agent_id) DO UPDATE SET source_hash = excluded.source_hash
                """,
                (Config.QDRANT_COLLECTION, agent_id, agent_hash(updated)),
            )
            connection.commit()
            return updated
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def status(self) -> dict:
        indexed_agents = [agent for agent in self.components.agent_store.all() if agent.utterances]
        expected_hashes = {agent.id: agent_hash(agent) for agent in indexed_agents}
        expected_points = sum(
            len(agent.utterances) + len(agent.negative_samples) for agent in indexed_agents
        )
        actual = self.components.qdrant_client.index_summary()
        synced = (
            bool(indexed_agents)
            and actual["points_count"] == expected_points
            and actual["route_ids"] == sorted(expected_hashes)
            and actual["route_hashes"] == expected_hashes
        )
        return {
            "agents_count": len(self.components.agent_store.all()),
            "collection": Config.QDRANT_COLLECTION,
            "expected_points": expected_points,
            "points_count": actual["points_count"],
            "synced": synced,
        }
