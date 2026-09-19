"""Persistent request records for the first logging vertical slice."""

import json
import logging
import math
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from flask import g, has_request_context, jsonify, request

from intent_hub.config import Config
from intent_hub.utils.logger import logger
from intent_hub.utils.log_context import CATEGORIES, classify_log, log_category


def record_category(kind, payload):
    data = json.loads(payload) if isinstance(payload, str) else payload
    return data.get("category") or classify_log(
        kind, data.get("path", ""), data.get("source", ""), data.get("message", ""))


class LogStore:
    def __init__(self, path):
        self.path = Path(path)

    def connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.path, timeout=0.2)
        db.row_factory = sqlite3.Row
        db.create_function("record_category", 2, record_category, deterministic=True)
        try:
            db.execute("""CREATE TABLE IF NOT EXISTS records (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                created_at REAL NOT NULL, request_id TEXT NOT NULL,
                payload TEXT NOT NULL)""")
            db.execute("CREATE INDEX IF NOT EXISTS logs_kind_time ON records(kind, created_at, id)")
            db.execute("CREATE INDEX IF NOT EXISTS logs_request ON records(request_id)")
            db.commit()
        except Exception:
            db.close()
            raise
        return db

    def append(self, records):
        with closing(self.connect()) as db, db:
            db.executemany(
                "INSERT INTO records(kind, created_at, request_id, payload) VALUES (?, ?, ?, ?)",
                [(kind, created, rid, json.dumps(payload, ensure_ascii=False))
                 for kind, created, rid, payload in records],
            )

    def query(self, kind, request_id=None, page=1, page_size=20,
              keyword=None, level=None, start=None, end=None, category=None):
        where = "kind = ? AND created_at >= ?"
        values = [kind, time.time() - 30 * 86400]
        if request_id:
            where += " AND request_id = ?"
            values.append(request_id)
        if category:
            where += " AND record_category(kind, payload) = ?"
            values.append(category)
        if start is not None:
            where += " AND created_at >= ?"
            values.append(start)
        if end is not None:
            where += " AND created_at <= ?"
            values.append(end)
        if level:
            where += " AND json_extract(payload, '$.level') = ?"
            values.append(level)
        if keyword:
            field = "message" if kind == "runtime" else "input_text"
            where += f" AND instr(COALESCE(json_extract(payload, '$.{field}'), ''), ?) > 0"
            values.append(keyword)
        with closing(self.connect()) as db, db:
            total = db.execute(f"SELECT COUNT(*) FROM records WHERE {where}", values).fetchone()[0]
            rows = db.execute(
                f"SELECT * FROM records WHERE {where} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                [*values, page_size, (page - 1) * page_size],
            ).fetchall()
        return {"items": [{"id": row["id"], "created_at": row["created_at"],
                           "request_id": row["request_id"], **json.loads(row["payload"]),
                           "category": record_category(row["kind"], row["payload"]),
                           "category_inferred": "category" not in json.loads(row["payload"])}
                          for row in rows],
                "total": total, "page": page, "page_size": page_size}


def get_log_store():
    return LogStore(Path(Config.DATA_DIR) / "logs.sqlite3")


def redact_runtime(text):
    secrets = []
    for name in Config.SECRET_KEYS:
        value = getattr(Config, name, None)
        if isinstance(value, str) and value:
            secrets.append(value)
        elif isinstance(value, (list, tuple, set)):
            secrets.extend(v for v in value if isinstance(v, str) and v)
    if has_request_context():
        for name in ("Authorization", "X-API-Key"):
            value = request.headers.get(name, "")
            if value:
                secrets.append(value)
                if value.startswith("Bearer "):
                    secrets.append(value[7:])
    for secret in sorted(set(secrets), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    return text


class PersistentLogHandler(logging.Handler):
    def emit(self, record):
        try:
            rid = getattr(g, "log_request_id", "") if has_request_context() else ""
            payload = {"level": record.levelname, "module": record.name,
                       "source": record.module,
                       "category": getattr(record, "category", None) or log_category.get() or (
                           getattr(g, "log_category", None) if has_request_context() else None
                       ) or classify_log(source=record.module),
                       "message": redact_runtime(record.getMessage()),
                       "exception": redact_runtime(logging.Formatter().formatException(record.exc_info))
                       if record.exc_info else None}
            for field in ("task_id", "task_status", "attempt", "elapsed_ms", "queue_wait_ms", "lock_wait_ms"):
                if hasattr(record, field):
                    payload[field] = getattr(record, field)
            get_log_store().append([("runtime", record.created, rid, payload)])
        except Exception:
            # Never send storage failures back through this same handler.
            try:
                sys.stderr.write("Application log persistence failed\n")
            except Exception:
                pass


def install_request_logging(app):
    if not any(isinstance(handler, PersistentLogHandler) for handler in logger.handlers):
        logger.addHandler(PersistentLogHandler())
    if not any(isinstance(handler, PersistentLogHandler) for handler in app.logger.handlers):
        app.logger.addHandler(PersistentLogHandler())

    @app.before_request
    def start_request_record():
        g.log_request_id = uuid4().hex
        g.log_started = time.monotonic()
        g.log_created = time.time()
        g.log_category = classify_log(path=request.path)

    @app.after_request
    def finish_request_record(response):
        response.headers["X-Request-ID"] = g.log_request_id
        payload = {"method": request.method, "path": request.path,
                   "category": g.log_category,
                   "status_code": response.status_code,
                   "elapsed_ms": round((time.monotonic() - g.log_started) * 1000, 3)}
        records = [("runtime", g.log_created, g.log_request_id, {
            **payload, "level": "ERROR" if response.status_code >= 500 else (
                "WARNING" if response.status_code >= 400 else "INFO"),
            "message": "Request completed"})]
        if hasattr(g, "route_input"):
            records.append(("routing", g.log_created, g.log_request_id, {
                **payload, "input_text": g.route_input,
                "status": "succeeded" if response.status_code < 400 else "failed",
                "result": response.get_json(silent=True) if response.status_code < 400 else None,
                "events": getattr(g, "route_events", []),
                "timings": getattr(g, "route_timings", []),
            }))
        try:
            get_log_store().append(records)
        except Exception as exc:
            # Do not include database errors or request content in this fallback.
            logger.warning("Request log persistence failed (%s)", type(exc).__name__)
        return response


def list_records(kind):
    if kind not in {"runtime", "routing"}:
        return jsonify({"error": "Unknown log kind"}), 404
    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError
        start = float(request.args["start"]) if request.args.get("start") else None
        end = float(request.args["end"]) if request.args.get("end") else None
        if any(value is not None and not math.isfinite(value) for value in (start, end)):
            raise ValueError
        if start is not None and end is not None and start > end:
            raise ValueError
        level = request.args.get("level") or None
        category = request.args.get("category") or None
        if category and category not in CATEGORIES:
            raise ValueError
        if level and (kind != "runtime" or level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}):
            raise ValueError
    except ValueError:
        return jsonify({"error": "Invalid pagination, category, level or time range"}), 400
    try:
        return jsonify(get_log_store().query(kind, request.args.get("request_id"), page, page_size,
                                            request.args.get("keyword"), level, start, end, category))
    except Exception as exc:
        logger.warning("Log query failed (%s)", type(exc).__name__)
        return jsonify({"error": "Log storage unavailable"}), 503
