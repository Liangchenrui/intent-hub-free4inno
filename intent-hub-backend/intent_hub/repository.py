"""Single SQLite source of truth; mutations and sync intent commit together."""
from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from intent_hub.models import RouteConfig


class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS entities (
                    id INTEGER PRIMARY KEY, route_key TEXT UNIQUE NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS identity (
                    contract TEXT NOT NULL, source TEXT NOT NULL, legacy_id INTEGER NOT NULL,
                    entity_id INTEGER NOT NULL, PRIMARY KEY(contract, source, legacy_id));
                CREATE TABLE IF NOT EXISTS outbox (entity_id INTEGER PRIMARY KEY, token TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                INSERT OR IGNORE INTO metadata VALUES ('schema_version', '1');
                INSERT OR IGNORE INTO metadata VALUES ('sequence', '0');
            ''')
            if 'token' not in {r[1] for r in db.execute('PRAGMA table_info(outbox)')}:
                db.execute("ALTER TABLE outbox ADD COLUMN token TEXT NOT NULL DEFAULT ''")
                db.execute("UPDATE outbox SET token=lower(hex(randomblob(16)))")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @contextmanager
    def transaction(self):
        with self._lock, self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            yield db

    def all(self):
        with self.connect() as db:
            return [RouteConfig.model_validate_json(row[0]) for row in db.execute('SELECT body FROM entities ORDER BY id')]

    def get(self, entity_id):
        with self.connect() as db:
            row = db.execute('SELECT body FROM entities WHERE id=?', (entity_id,)).fetchone()
        return RouteConfig.model_validate_json(row[0]) if row else None

    def save(self, route, db=None, enqueue=True):
        if db is None:
            with self.transaction() as connection:
                return self.save(route, connection, enqueue)
        row = db.execute('SELECT body FROM entities WHERE id=?', (route.id,)).fetchone()
        previous = RouteConfig.model_validate_json(row[0]) if row else None
        if previous and previous.sync and route.sync and route.sync.version < previous.sync.version:
            raise ValueError('Entity changed concurrently; reload before saving')
        db.execute('INSERT INTO entities VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET route_key=excluded.route_key,body=excluded.body',
                   (route.id, route.route_key, route.model_dump_json()))
        db.execute("UPDATE metadata SET value=CAST(MAX(CAST(value AS INTEGER), ?) AS TEXT) WHERE key='sequence'", (route.id,))
        if enqueue and (previous is None or previous.model_dump() != route.model_dump()):
            db.execute('INSERT INTO outbox VALUES (?,?) ON CONFLICT(entity_id) DO UPDATE SET token=excluded.token', (route.id, uuid.uuid4().hex))

    def delete(self, entity_id, db=None):
        if db is None:
            with self.transaction() as connection:
                return self.delete(entity_id, connection)
        changed = db.execute('DELETE FROM entities WHERE id=?', (entity_id,)).rowcount
        if changed:
            db.execute('INSERT INTO outbox VALUES (?,?) ON CONFLICT(entity_id) DO UPDATE SET token=excluded.token', (entity_id, uuid.uuid4().hex))
        return bool(changed)

    def allocate(self, db=None):
        if db is None:
            with self.transaction() as connection:
                return self.allocate(connection)
        db.execute("UPDATE metadata SET value=CAST(value AS INTEGER)+1 WHERE key='sequence'")
        return int(db.execute("SELECT value FROM metadata WHERE key='sequence'").fetchone()[0])

    def bind(self, contract, source, legacy_id, entity_id, db):
        old = db.execute('SELECT entity_id FROM identity WHERE contract=? AND source=? AND legacy_id=?', (contract, source, legacy_id)).fetchone()
        if old and old[0] != entity_id:
            raise ValueError('Conflicting legacy identity')
        db.execute('INSERT OR IGNORE INTO identity VALUES (?,?,?,?)', (contract, source, legacy_id, entity_id))

    def resolve(self, contract, source, legacy_id):
        with self.connect() as db:
            row = db.execute('SELECT entity_id FROM identity WHERE contract=? AND source=? AND legacy_id=?', (contract, source, legacy_id)).fetchone()
        return row[0] if row else None

    def legacy_id(self, contract, source, entity_id):
        with self.connect() as db:
            row = db.execute('SELECT legacy_id FROM identity WHERE contract=? AND source=? AND entity_id=?', (contract, source, entity_id)).fetchone()
        return row[0] if row else entity_id

    def metadata(self, key, value=None):
        with self.connect() as db:
            if value is not None:
                db.execute('INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
            row = db.execute('SELECT value FROM metadata WHERE key=?', (key,)).fetchone()
        return row[0] if row else None

    def pending(self):
        with self.connect() as db:
            return [row[0] for row in db.execute('SELECT entity_id FROM outbox')]

    def pending_tokens(self):
        with self.connect() as db:
            return {str(row[0]): row[1] for row in db.execute('SELECT entity_id,token FROM outbox')}

    def load_tasks(self):
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT body FROM tasks ORDER BY rowid')]

    def save_tasks(self, tasks):
        with self.transaction() as db:
            for task in tasks:
                db.execute('INSERT INTO tasks VALUES (?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body', (task['id'], json.dumps(task)))
                for entity_id, token in task.get('outbox_tokens', {}).items():
                    db.execute('DELETE FROM outbox WHERE entity_id=? AND token=?', (int(entity_id), token))
