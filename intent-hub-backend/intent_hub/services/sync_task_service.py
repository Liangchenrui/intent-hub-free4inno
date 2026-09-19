"""Persistent, single-worker background synchronization queue."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from intent_hub.config import Config
from intent_hub.services.sync_service import SyncService
from intent_hub.utils.logger import logger
from intent_hub.utils.log_context import log_scope


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SyncTaskService:
    """Persist route-sync intent before processing it on one daemon worker."""

    RETRY_DELAYS = (2, 5, 15, 30, 60)

    def __init__(
        self,
        component_manager,
        task_path: str | None = None,
        sync_service_factory: Callable[[Any], SyncService] = SyncService,
        autostart: bool = True,
        refresh_diagnostics: bool = True,
    ):
        self.component_manager = component_manager
        self.task_path = Path(task_path or Config.SYNC_TASKS_PATH)
        self.sync_service_factory = sync_service_factory
        self.max_attempts = max(1, int(Config.SYNC_MAX_ATTEMPTS))
        self._lock = threading.RLock()
        self._condition = threading.Condition(self._lock)
        self._processing = threading.Lock()
        self._tasks = self._load_tasks()
        self._worker: Optional[threading.Thread] = None
        self._stopped = False
        self._autostart = autostart
        self._refresh_diagnostics = refresh_diagnostics
        self._diagnostics_dirty = False
        self._recover_interrupted_tasks()
        self._recover_pending_routes()
        if self._autostart:
            self.start()

    @property
    def route_manager(self):
        """Follow component resets after runtime settings change."""
        return self.component_manager.route_manager

    def start(self) -> None:
        with self._condition:
            if self._worker is not None and self._worker.is_alive():
                self._condition.notify_all()
                return
            self._stopped = False
            self._worker = threading.Thread(
                target=self._worker_loop,
                name="intent-hub-sync-worker",
                daemon=True,
            )
            self._worker.start()

    def stop(self) -> None:
        with self._condition:
            self._stopped = True
            self._condition.notify_all()

    def enqueue_routes(self, route_ids: list[int]) -> dict[str, Any]:
        route_ids = list(dict.fromkeys(int(route_id) for route_id in route_ids))
        if not route_ids:
            raise ValueError("At least one route ID is required")

        repository = getattr(self.route_manager, "repository", None)
        tokens = repository.pending_tokens() if repository else {}
        versions: dict[str, int] = {}
        for route_id in route_ids:
            route = self.route_manager.get_route(route_id)
            versions[str(route_id)] = route.sync.version if route and route.sync else 0

        with self._condition:
            queued = next(
                (
                    task
                    for task in reversed(self._tasks)
                    if task["kind"] == "route_sync" and task["status"] == "queued" and task.get("target") == self._target()
                ),
                None,
            )
            if queued is None:
                queued = {
                    "id": uuid.uuid4().hex,
                    "target": self._target(),
                    "kind": "route_sync",
                    "route_ids": [],
                    "route_versions": {},
                    "status": "queued",
                    "attempts": 0,
                    "next_attempt_at": 0.0,
                    "created_at": _utc_now(),
                    "updated_at": _utc_now(),
                    "error": None,
                }
                self._tasks.append(queued)

            queued["route_ids"] = list(dict.fromkeys(queued["route_ids"] + route_ids))
            queued["route_versions"].update(versions)
            queued.setdefault("outbox_tokens", {}).update({str(i): tokens[str(i)] for i in route_ids if str(i) in tokens})
            queued["updated_at"] = _utc_now()
            queued["error"] = None
            queued["next_attempt_at"] = 0.0
            self._save_tasks()

            for route_id in route_ids:
                route = self.route_manager.get_route(route_id)
                if route is not None and route.sync is not None:
                    self.route_manager.update_sync_state(
                        route_id,
                        status="queued",
                        task_id=queued["id"],
                        error=None,
                    )

            if self._autostart:
                self.start()
            self._condition.notify_all()
            return dict(queued)

    def enqueue_incremental_reindex(self) -> dict[str, Any]:
        return self.enqueue_reindex(False)

    def enqueue_upstream_pull(self) -> dict[str, Any]:
        from intent_hub.services.upstream_agent_service import UpstreamAgentService
        source = UpstreamAgentService.source_config()
        if not source['AGENT_API_URL'] or not source['AGENT_API_LABEL_IDS']:
            raise ValueError('请先配置上游地址和标签')
        with self._condition:
            task = next((t for t in reversed(self._tasks)
                         if t['kind'] == 'upstream_pull' and t['status'] in {'queued', 'running'}
                         and t.get('source_config') == source), None)
            if task is None:
                task = dict(id=uuid.uuid4().hex, kind='upstream_pull', source_config=source,
                            route_ids=[], route_versions={}, status='queued', phase='fetching',
                            attempts=0, next_attempt_at=0.0, created_at=_utc_now(),
                            updated_at=_utc_now(), error=None, result=None)
                self._tasks.append(task)
                self._save_tasks()
            if self._autostart:
                self.start()
            self._condition.notify_all()
            return dict(task)

    def enqueue_reindex(self, full=False) -> dict[str, Any]:
        """Queue one hash-based index scan without touching remote services."""
        with self._condition:
            queued = next(
                (
                    task
                    for task in reversed(self._tasks)
                    if task["kind"] == ("full_reindex" if full else "incremental_reindex")
                    and task["status"] == "queued"
                    and task.get("target") == self._target()
                ),
                None,
            )
            if queued is None:
                queued = {
                    "id": uuid.uuid4().hex,
                    "target": self._target(),
                    "kind": "full_reindex" if full else "incremental_reindex",
                    "route_ids": [],
                    "route_versions": {},
                    "status": "queued",
                    "attempts": 0,
                    "next_attempt_at": 0.0,
                    "created_at": _utc_now(),
                    "updated_at": _utc_now(),
                    "error": None,
                    "result": None,
                }
                self._tasks.append(queued)
            else:
                queued["updated_at"] = _utc_now()
                queued["error"] = None
                queued["next_attempt_at"] = 0.0

            self._save_tasks()
            if self._autostart:
                self.start()
            self._condition.notify_all()
            return dict(queued)

    def list_tasks(self, active_only: bool = False) -> list[dict[str, Any]]:
        with self._lock:
            tasks = self._tasks
            if active_only:
                tasks = [task for task in tasks if task["status"] in {"queued", "running"}]
            return [dict(task) for task in tasks]

    def retry(self, task_id: str) -> dict[str, Any]:
        with self._condition:
            task = self._find_task(task_id)
            if task is None:
                raise ValueError(f"Sync task {task_id} does not exist")
            if task["status"] not in {"error", "superseded"}:
                raise ValueError(f"Sync task {task_id} cannot be retried from {task['status']}")
            task.update(
                status="queued",
                attempts=0,
                next_attempt_at=0.0,
                queued_at=_utc_now(),
                updated_at=_utc_now(),
                error=None,
            )
            self._set_route_status(task, "queued")
            self._save_tasks()
            if self._autostart:
                self.start()
            self._condition.notify_all()
            return dict(task)

    def supersede_queued(self, reason: str) -> None:
        """Cancel queued work after an authoritative index/config replacement."""
        with self._condition:
            changed = False
            for task in self._tasks:
                if task["status"] == "queued":
                    task["status"] = "superseded"
                    task["error"] = reason
                    task["updated_at"] = _utc_now()
                    changed = True
            if changed:
                self._save_tasks()
                self._condition.notify_all()

    @staticmethod
    def _target():
        return {key: getattr(Config, key) for key in (
            "QDRANT_URL", "QDRANT_COLLECTION", "EMBEDDING_SERVICE_URL",
            "EMBEDDING_MODEL_NAME", "EMBEDDING_API_FORMAT")}

    def process_next(self) -> bool:
        with self._processing, log_scope("sync"):
            return self._process_next()

    def _process_next(self) -> bool:
        """Process one ready task; exposed for deterministic unit tests."""
        with self._condition:
            task = self._next_ready_task()
            if task is None:
                return False
            task["status"] = "running"
            task["attempts"] += 1
            task["updated_at"] = _utc_now()
            task["started_at"] = task["updated_at"]
            queued_at = task.get("queued_at", task["created_at"])
            task["queue_wait_ms"] = max(0, round(
                (datetime.fromisoformat(task["started_at"]) - datetime.fromisoformat(queued_at)).total_seconds() * 1000, 3))
            self._set_route_status(task, "syncing")
            self._save_tasks()

        started = time.perf_counter()
        try:
            self._execute_task(task)
        except Exception as exc:
            task["execution_ms"] = round((time.perf_counter() - started) * 1000, 3)
            self._handle_failure(task, exc)
        else:
            with self._condition:
                task["execution_ms"] = round((time.perf_counter() - started) * 1000, 3)
                if task["status"] != "superseded":
                    task["status"] = "succeeded"
                task["updated_at"] = _utc_now()
                task["error"] = None
                self._save_tasks()
            if task["kind"] == "route_sync" and task.get("index_changed", True):
                self._diagnostics_dirty = True
            if self._diagnostics_dirty:
                self._refresh_diagnostics_if_idle()
        logger.info("Sync task %s status=%s attempt=%s", task["id"], task["status"], task["attempts"],
                    extra={"category": "sync", "task_id": task["id"], "task_status": task["status"],
                           "attempt": task["attempts"], "elapsed_ms": task["execution_ms"],
                           "queue_wait_ms": task.get("queue_wait_ms"), "lock_wait_ms": task.get("lock_wait_ms")})
        return True

    def _execute_task(self, task: dict[str, Any]) -> None:
        if task['kind'] == 'upstream_pull':
            from intent_hub.agent_source import AgentSource
            from intent_hub.services.upstream_agent_service import UpstreamAgentService
            source = task['source_config']
            if source != UpstreamAgentService.source_config():
                task['status'] = 'superseded'
                return
            def progress(phase):
                with self._condition:
                    task['phase'] = phase
                    self._save_tasks()
            progress('fetching')
            result = UpstreamAgentService(self.component_manager, source=AgentSource(
                label_ids=source['AGENT_API_LABEL_IDS'], base_url=source['AGENT_API_URL']
            )).pull(progress=progress, expected_source=source)
            task['result'] = result
            # Also reconnect durable pending work after a crash between local commit
            # and linking the index task, including an unchanged retry of the pull.
            ids = sorted(set(result['affected_route_ids']) | {
                r.id for r in self.route_manager.get_all_routes()
                if r.source and r.source.type == 'upstream_agent'
                and r.source.instance == source['SOURCE_INSTANCE']
                and r.sync and r.sync.version != r.sync.synced_version
            })
            if ids:
                result['sync_task_id'] = self.enqueue_routes(ids)['id']
            task['phase'] = 'saved'
            return
        lock_started = time.perf_counter()
        with SyncService.execution_lock:
            task['lock_wait_ms'] = round((time.perf_counter() - lock_started) * 1000, 3)
            if task.get("target") != self._target():
                task["status"] = "superseded"
                return
            if task["kind"] in {"incremental_reindex", "full_reindex"}:
                sync_service = self.sync_service_factory(self.component_manager)
                task["result"] = sync_service.reindex(force_full=task["kind"] == "full_reindex")
                return
            self._execute_route_task_locked(task)

    def _execute_route_task_locked(self, task: dict[str, Any]) -> None:
        sync_service = self.sync_service_factory(self.component_manager)
        synced_any = False
        superseded_any = False
        task['index_changed'] = False

        for route_id in task["route_ids"]:
            expected_version = int(task["route_versions"].get(str(route_id), 0))
            route = self.route_manager.get_route(route_id)
            if route is not None and route.sync and route.sync.version != expected_version:
                superseded_any = True
                continue

            if route is None:
                qdrant = self.component_manager.qdrant_client
                qdrant.delete_route(route_id)
                task['index_changed'] = True
                synced_any = True
                continue

            result = sync_service.sync_route(route_id)
            task['index_changed'] |= not isinstance(result, dict) or result.get('changed', True)
            if isinstance(result, dict):
                task["result"] = task.get("result") or {}
                task["result"].setdefault("routes", {})[str(route_id)] = result
            latest = self.route_manager.get_route(route_id)
            if latest is None or latest.sync is None or latest.sync.version != expected_version:
                superseded_any = True
                continue

            latest = self.route_manager.update_sync_state(
                route_id,
                status="synced",
                synced_version=expected_version,
                last_synced_at=_utc_now(),
                task_id=task["id"],
                error=None,
                **({'expected_version': expected_version} if hasattr(self.route_manager, 'repository') else {}),
            )
            if latest is not None and not (isinstance(result, dict) and result.get("metadata_committed")):
                self.component_manager.qdrant_client.update_route_metadata_state(latest)
            synced_any = True

        if superseded_any and not synced_any:
            task["status"] = "superseded"

    def _handle_failure(self, task: dict[str, Any], exc: Exception) -> None:
        error = str(exc)
        logger.error("Background route sync failed: %s", error, exc_info=True)
        with self._condition:
            task["error"] = error
            task["updated_at"] = _utc_now()
            if task["attempts"] < self.max_attempts:
                delay_index = min(task["attempts"] - 1, len(self.RETRY_DELAYS) - 1)
                task["status"] = "queued"
                task["queued_at"] = _utc_now()
                task["next_attempt_at"] = time.time() + self.RETRY_DELAYS[delay_index]
                self._set_route_status(task, "queued", error)
            else:
                task["status"] = "error"
                self._set_route_status(task, "error", error)
            self._save_tasks()
            self._condition.notify_all()

    def _set_route_status(self, task: dict[str, Any], status: str, error: str | None = None) -> None:
        for route_id in task["route_ids"]:
            route = self.route_manager.get_route(route_id)
            expected = int(task["route_versions"].get(str(route_id), 0))
            if route is not None and route.sync is not None and route.sync.version == expected:
                self.route_manager.update_sync_state(
                    route_id,
                    status=status,
                    task_id=task["id"],
                    error=error,
                    **({'expected_version': expected} if hasattr(self.route_manager, 'repository') else {}),
                )

    def _worker_loop(self) -> None:
        while True:
            with self._condition:
                if self._stopped:
                    return
                task = self._next_ready_task()
                if task is None:
                    self._recover_pending_routes()
                    task = self._next_ready_task()
                if task is None:
                    self._condition.wait(timeout=self._seconds_until_next_task())
                    continue
            self.process_next()

    def _next_ready_task(self) -> Optional[dict[str, Any]]:
        now = time.time()
        return next(
            (
                task
                for task in self._tasks
                if task["status"] == "queued" and task.get("next_attempt_at", 0) <= now
            ),
            None,
        )

    def _seconds_until_next_task(self) -> float:
        scheduled = [
            max(0.1, task.get("next_attempt_at", 0) - time.time())
            for task in self._tasks
            if task["status"] == "queued"
        ]
        return min(scheduled, default=30.0)

    def _refresh_diagnostics_if_idle(self) -> None:
        if not self._refresh_diagnostics:
            return
        with self._lock:
            if any(task["status"] in {"queued", "running"} for task in self._tasks):
                return
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService

            DiagnosticService(self.component_manager).run_async_diagnostics("full")
            self._diagnostics_dirty = False
        except Exception as exc:  # diagnostics never changes sync success
            logger.error("Failed to schedule diagnostics refresh: %s", exc)

    def _recover_interrupted_tasks(self) -> None:
        changed = False
        for task in self._tasks:
            if task.get("status") == "running":
                task["status"] = "queued"
                task["queued_at"] = _utc_now()
                task["next_attempt_at"] = 0.0
                changed = True
        if changed:
            self._save_tasks()

    def _recover_pending_routes(self) -> None:
        queued_ids = {
            route_id
            for task in self._tasks
            if task.get("status") in {"queued", "running"}
            for route_id in task.get("route_ids", [])
        }
        repository = getattr(self.route_manager, "repository", None)
        outbox = repository.pending() if repository else []
        missing = [
            route.id
            for route in self.route_manager.get_all_routes()
            if route.sync is not None
            and route.sync.status in {"pending", "queued", "syncing"}
            and route.id not in queued_ids
        ]
        missing = list(set(missing) | set(outbox))
        if missing:
            self.enqueue_routes(missing)

    def _load_tasks(self) -> list[dict[str, Any]]:
        repository = getattr(self.route_manager, "repository", None)
        if repository:
            return repository.load_tasks()
        # Only test doubles without a repository use the legacy task file.
        return json.loads(self.task_path.read_text(encoding="utf-8")) if self.task_path.exists() else []

    def _save_tasks(self) -> None:
        repository = getattr(self.route_manager, "repository", None)
        if repository:
            repository.save_tasks(self._tasks)
            return
        self.task_path.parent.mkdir(parents=True, exist_ok=True)
        self.task_path.write_text(json.dumps(self._tasks), encoding="utf-8")

    def _find_task(self, task_id: str) -> Optional[dict[str, Any]]:
        return next((task for task in self._tasks if task["id"] == task_id), None)


_service: Optional[SyncTaskService] = None
_service_lock = threading.Lock()


def get_sync_task_service(component_manager=None) -> SyncTaskService:
    global _service
    with _service_lock:
        if _service is None:
            if component_manager is None:
                from intent_hub.core.components import get_component_manager

                component_manager = get_component_manager()
            _service = SyncTaskService(component_manager)
        return _service
