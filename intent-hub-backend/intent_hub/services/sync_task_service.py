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
        self._tasks = self._load_tasks()
        self._worker: Optional[threading.Thread] = None
        self._stopped = False
        self._autostart = autostart
        self._refresh_diagnostics = refresh_diagnostics
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

        versions: dict[str, int] = {}
        for route_id in route_ids:
            route = self.route_manager.get_route(route_id)
            versions[str(route_id)] = route.sync.version if route and route.sync else 0

        with self._condition:
            queued = next(
                (
                    task
                    for task in reversed(self._tasks)
                    if task["kind"] == "route_sync" and task["status"] == "queued"
                ),
                None,
            )
            if queued is None:
                queued = {
                    "id": uuid.uuid4().hex,
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
        """Queue one hash-based index scan without touching remote services."""
        with self._condition:
            queued = next(
                (
                    task
                    for task in reversed(self._tasks)
                    if task["kind"] == "incremental_reindex"
                    and task["status"] == "queued"
                ),
                None,
            )
            if queued is None:
                queued = {
                    "id": uuid.uuid4().hex,
                    "kind": "incremental_reindex",
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

    def process_next(self) -> bool:
        """Process one ready task; exposed for deterministic unit tests."""
        with self._condition:
            task = self._next_ready_task()
            if task is None:
                return False
            task["status"] = "running"
            task["attempts"] += 1
            task["updated_at"] = _utc_now()
            self._set_route_status(task, "syncing")
            self._save_tasks()

        try:
            self._execute_task(task)
        except Exception as exc:
            self._handle_failure(task, exc)
        else:
            with self._condition:
                if task["status"] != "superseded":
                    task["status"] = "succeeded"
                task["updated_at"] = _utc_now()
                task["error"] = None
                self._save_tasks()
            if task["kind"] != "incremental_reindex":
                self._refresh_diagnostics_if_idle()
        return True

    def _execute_task(self, task: dict[str, Any]) -> None:
        with SyncService.execution_lock:
            if task["kind"] == "incremental_reindex":
                sync_service = self.sync_service_factory(self.component_manager)
                task["result"] = sync_service.reindex(force_full=False)
                return
            self._execute_route_task_locked(task)

    def _execute_route_task_locked(self, task: dict[str, Any]) -> None:
        sync_service = self.sync_service_factory(self.component_manager)
        synced_any = False
        superseded_any = False

        for route_id in task["route_ids"]:
            expected_version = int(task["route_versions"].get(str(route_id), 0))
            route = self.route_manager.get_route(route_id)
            if route is not None and route.sync and route.sync.version != expected_version:
                superseded_any = True
                continue

            if route is None:
                qdrant = self.component_manager.qdrant_client
                qdrant.delete_route(route_id)
                synced_any = True
                continue

            sync_service.sync_route(route_id)
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
            )
            if latest is not None:
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
        except Exception as exc:  # diagnostics never changes sync success
            logger.error("Failed to schedule diagnostics refresh: %s", exc)

    def _recover_interrupted_tasks(self) -> None:
        changed = False
        for task in self._tasks:
            if task.get("status") == "running":
                task["status"] = "queued"
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
        missing = [
            route.id
            for route in self.route_manager.get_all_routes()
            if route.sync is not None
            and route.sync.status in {"pending", "queued", "syncing"}
            and route.id not in queued_ids
        ]
        if missing:
            self.enqueue_routes(missing)

    def _load_tasks(self) -> list[dict[str, Any]]:
        if not self.task_path.exists():
            return []
        try:
            data = json.loads(self.task_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.error("Failed to load sync tasks: %s", exc)
            return []

    def _save_tasks(self) -> None:
        self.task_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(prefix="sync-tasks-", suffix=".tmp", dir=self.task_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._tasks, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.task_path)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

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
