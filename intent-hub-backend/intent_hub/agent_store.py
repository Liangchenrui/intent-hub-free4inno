"""SQLite-backed local Agent repository."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock

from intent_hub.agent_compare import COMPARABLE_FIELDS, snapshots_equal
from intent_hub.models import Agent


JSON_FIELDS = ("utterances", "negative_samples", "details", "manual_overrides", "source_snapshot")
EDITABLE_FIELDS = {"title", "text", "utterances", "negative_samples", "score_threshold", "negative_threshold", "lifecycle_status"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AgentStore:
    def __init__(self, path: Path, legacy_path: Path | None = None):
        self.path = Path(path)
        self.legacy_path = legacy_path
        self._lock = RLock()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()
        self._migrate_legacy()

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_schema(self) -> None:
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS agents (
                    id INTEGER PRIMARY KEY,
                    upstream_id INTEGER UNIQUE,
                    source_type TEXT NOT NULL DEFAULT 'upstream',
                    upstream_present INTEGER,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL DEFAULT '',
                    utterances TEXT NOT NULL DEFAULT '[]',
                    negative_samples TEXT NOT NULL DEFAULT '[]',
                    score_threshold REAL NOT NULL DEFAULT 0.8,
                    negative_threshold REAL NOT NULL DEFAULT 0.95,
                    details TEXT NOT NULL DEFAULT '{}',
                    manual_overrides TEXT NOT NULL DEFAULT '[]',
                    lifecycle_status TEXT NOT NULL DEFAULT 'active',
                    source_snapshot TEXT NOT NULL DEFAULT '{}',
                    updated_at TEXT NOT NULL
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)
            """)
            columns = {row[1] for row in connection.execute("PRAGMA table_info(agents)")}
            if "upstream_present" not in columns:
                connection.execute("ALTER TABLE agents ADD COLUMN upstream_present INTEGER")

    def _migrate_legacy(self) -> None:
        if not self.legacy_path or not self.legacy_path.exists() or self.all():
            return
        raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
        self.replace([Agent(**item) for item in raw])
        self.set_metadata("legacy_agents_json_migrated", now_iso())

    @staticmethod
    def _from_row(row: sqlite3.Row) -> Agent:
        data = dict(row)
        for field in JSON_FIELDS:
            data[field] = json.loads(data[field] or ("[]" if field in {"utterances", "negative_samples", "manual_overrides"} else "{}"))
        return Agent(**data)

    def all(self, include_inactive: bool = True) -> list[Agent]:
        sql = "SELECT * FROM agents"
        if not include_inactive:
            sql += " WHERE lifecycle_status = 'active'"
        sql += " ORDER BY id"
        with self._lock, self._connect() as connection:
            return [self._from_row(row) for row in connection.execute(sql)]

    def active(self) -> list[Agent]:
        return self.all(include_inactive=False)

    def get(self, agent_id: int) -> Agent | None:
        with self._lock, self._connect() as connection:
            row = connection.execute("SELECT * FROM agents WHERE id = ?", (agent_id,)).fetchone()
            return self._from_row(row) if row else None

    def _save(self, connection, agent: Agent) -> None:
        data = agent.model_dump()
        data["upstream_id"] = data.get("upstream_id") if data.get("upstream_id") is not None else (agent.id if agent.source_type == "upstream" else None)
        data["updated_at"] = data.get("updated_at") or now_iso()
        for field in JSON_FIELDS:
            data[field] = json.dumps(data.get(field), ensure_ascii=False)
        connection.execute("""
            INSERT INTO agents (id, upstream_id, source_type, upstream_present, title, text, utterances,
                negative_samples, score_threshold, negative_threshold, details,
                manual_overrides, lifecycle_status, source_snapshot, updated_at)
            VALUES (:id, :upstream_id, :source_type, :upstream_present, :title, :text, :utterances,
                :negative_samples, :score_threshold, :negative_threshold, :details,
                :manual_overrides, :lifecycle_status, :source_snapshot, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                upstream_id=excluded.upstream_id, source_type=excluded.source_type,
                upstream_present=excluded.upstream_present,
                title=excluded.title, text=excluded.text, utterances=excluded.utterances,
                negative_samples=excluded.negative_samples, score_threshold=excluded.score_threshold,
                negative_threshold=excluded.negative_threshold, details=excluded.details,
                manual_overrides=excluded.manual_overrides, lifecycle_status=excluded.lifecycle_status,
                source_snapshot=excluded.source_snapshot, updated_at=excluded.updated_at
        """, data)

    def replace(self, agents: list[Agent]) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("DELETE FROM agents")
            for agent in agents:
                self._save(connection, agent)

    def upsert(self, agent: Agent) -> Agent:
        updated = agent.model_copy(update={"updated_at": now_iso()})
        with self._lock, self._connect() as connection:
            self._save(connection, updated)
        return updated

    def create_local(self, **values) -> Agent:
        with self._lock, self._connect() as connection:
            minimum = connection.execute("SELECT MIN(id) FROM agents WHERE id < 0").fetchone()[0]
            agent_id = (minimum - 1) if minimum is not None else -1
            agent = Agent(id=agent_id, source_type="local", upstream_id=None, details={}, **values)
            self._save(connection, agent.model_copy(update={"updated_at": now_iso()}))
        return self.get(agent_id)

    def update(self, agent_id: int, values: dict, track_overrides: bool = True) -> Agent:
        current = self.get(agent_id)
        if current is None:
            raise ValueError("Agent 不存在")
        values = {key: value for key, value in values.items() if key in EDITABLE_FIELDS and value is not None}
        overrides = set(current.manual_overrides)
        if track_overrides and current.source_type == "upstream":
            overrides.update(values)
        values["manual_overrides"] = sorted(overrides)
        return self.upsert(current.model_copy(update=values))

    def restore_fields(self, agent_id: int, fields: list[str]) -> Agent:
        current = self.get(agent_id)
        if current is None or current.source_type != "upstream":
            raise ValueError("只能恢复上游 Agent 字段")
        snapshot = current.source_snapshot
        allowed = set(fields) & {"title", "text", "utterances", "negative_samples"}
        values = {field: snapshot[field] for field in allowed if field in snapshot}
        values["manual_overrides"] = sorted(set(current.manual_overrides) - allowed)
        return self.upsert(current.model_copy(update=values))

    def merge_upstream(self, incoming: list[Agent]) -> dict:
        existing = {agent.id: agent for agent in self.all() if agent.source_type == "upstream"}
        incoming_ids = {agent.id for agent in incoming}
        created = upstream_changed = unchanged = preserved = upstream_missing = 0
        for source in incoming:
            snapshot = {key: getattr(source, key) for key in COMPARABLE_FIELDS}
            current = existing.get(source.id)
            if current is None:
                self.upsert(source.model_copy(update={
                    "upstream_id": source.id,
                    "upstream_present": True,
                    "source_snapshot": snapshot,
                }))
                created += 1
                continue
            changed = not snapshots_equal(current.source_snapshot or {}, snapshot)
            upstream_changed += int(changed)
            unchanged += int(not changed)
            values = {"details": source.details, "source_snapshot": snapshot, "upstream_present": True}
            for field, value in snapshot.items():
                if field in current.manual_overrides:
                    preserved += 1
                else:
                    values[field] = value
            if current.lifecycle_status == "inactive" and "lifecycle_status" not in current.manual_overrides:
                values["lifecycle_status"] = "active"
            self.upsert(current.model_copy(update=values))
        for agent_id, current in existing.items():
            if agent_id not in incoming_ids and current.upstream_present is not False:
                self.upsert(current.model_copy(update={"upstream_present": False, "lifecycle_status": "inactive"}))
                upstream_missing += 1
        return {
            "created": created,
            "updated": upstream_changed,
            "upstream_changed": upstream_changed,
            "unchanged": unchanged,
            "preserved_overrides": preserved,
            "disabled": upstream_missing,
            "upstream_missing": upstream_missing,
            "agents_count": len(self.all()),
        }

    def set_metadata(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute("INSERT INTO metadata(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def get_metadata(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute("SELECT value FROM metadata WHERE key = ?", (key,)).fetchone()
            return row[0] if row else None
