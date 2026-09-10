from __future__ import annotations

from intent_hub.config import Config
from intent_hub.app import app
from intent_hub.api import reindex as reindex_api
from intent_hub.core.components import ComponentManager
from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager
from intent_hub.services.route_service import RouteService
from intent_hub.services.sync_task_service import SyncTaskService


def make_route(route_id: int, name: str = "Orders") -> RouteConfig:
    return RouteConfig(
        id=route_id,
        name=name,
        route_key=name.lower(),
        description="Track orders",
        utterances=["Where is my order?"],
        sync=RouteConfig.RouteSync(status="pending", version=1),
    )


class FakeQdrant:
    def __init__(self):
        self.deleted = []
        self.metadata = []

    def delete_route(self, route_id):
        self.deleted.append(route_id)

    def update_route_metadata_state(self, route):
        self.metadata.append(route.model_copy(deep=True))


class FakeManager:
    def __init__(self, route_manager):
        self.route_manager = route_manager
        self.qdrant_client = FakeQdrant()


class RecordingSync:
    calls = []
    reindex_calls = []

    def __init__(self, _manager):
        pass

    def sync_route(self, route_id):
        self.calls.append(route_id)

    def reindex(self, force_full=False):
        self.reindex_calls.append(force_full)
        return {
            "mode": "incremental",
            "routes_count": 2,
            "updated_routes": 1,
            "skipped_routes": 1,
        }


class FailingSync:
    def __init__(self, _manager):
        pass

    def sync_route(self, _route_id):
        raise RuntimeError("qdrant unavailable")


def test_route_save_never_initializes_remote_components(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "ROUTES_CONFIG_PATH", str(tmp_path / "routes.json"))
    (tmp_path / "routes.json").write_text("[]", encoding="utf-8")

    def fail_remote(**_kwargs):
        raise AssertionError("remote Qdrant must not be initialized by route CRUD")

    manager = ComponentManager(qdrant_client_factory=fail_remote)
    saved = RouteService(manager).create_route(make_route(0))

    assert saved.id == 1
    assert saved.sync.status == "pending"
    assert saved.sync.version == 1


def test_delete_preserves_ids_and_sync_metadata_does_not_change_hash(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    manager.add_route(make_route(1, "One"))
    manager.add_route(make_route(2, "Two"))
    manager.add_route(make_route(3, "Three"))

    route = manager.get_route(2)
    before = manager.compute_route_hash(route)
    manager.update_sync_state(2, status="synced", synced_version=1, task_id="task")
    after = manager.compute_route_hash(manager.get_route(2))
    manager.delete_route(1)

    assert before == after
    assert [item.id for item in manager.get_all_routes()] == [2, 3]

    manager.delete_route(3)
    restarted = RouteManager(str(path))
    assert restarted.allocate_route_id() == 4


def test_queue_coalesces_latest_versions_and_marks_route_synced(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    route_manager = RouteManager(str(path))
    route_manager.add_route(make_route(1))
    manager = FakeManager(route_manager)
    RecordingSync.calls = []
    service = SyncTaskService(
        manager,
        task_path=str(tmp_path / "sync_tasks.json"),
        sync_service_factory=RecordingSync,
        autostart=False,
        refresh_diagnostics=False,
    )

    first = service.enqueue_routes([1])
    route_manager.update_sync_state(1, version=2, status="pending")
    second = service.enqueue_routes([1])

    assert first["id"] == second["id"]
    assert second["route_versions"] == {"1": 2}
    assert service.process_next() is True
    assert RecordingSync.calls == [1]
    route = route_manager.get_route(1)
    assert route.sync.status == "synced"
    assert route.sync.synced_version == 2
    assert service.list_tasks()[0]["status"] == "succeeded"


def test_incremental_reindex_queue_coalesces_and_records_result(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = FakeManager(RouteManager(str(path)))
    RecordingSync.reindex_calls = []
    service = SyncTaskService(
        manager,
        task_path=str(tmp_path / "sync_tasks.json"),
        sync_service_factory=RecordingSync,
        autostart=False,
        refresh_diagnostics=False,
    )

    first = service.enqueue_incremental_reindex()
    second = service.enqueue_incremental_reindex()

    assert first["id"] == second["id"]
    assert service.process_next() is True
    assert RecordingSync.reindex_calls == [False]
    task = service.list_tasks()[0]
    assert task["status"] == "succeeded"
    assert task["result"] == {
        "mode": "incremental",
        "routes_count": 2,
        "updated_routes": 1,
        "skipped_routes": 1,
    }


def test_reindex_api_queues_without_initializing_remote_components(monkeypatch):
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)

    class LocalOnlyManager:
        def ensure_ready(self):
            raise AssertionError("remote components must be initialized by the worker")

    class Queue:
        def enqueue_incremental_reindex(self):
            return {
                "id": "incremental-1",
                "kind": "incremental_reindex",
                "route_ids": [],
                "status": "queued",
                "attempts": 0,
                "error": None,
            }

    manager = LocalOnlyManager()
    monkeypatch.setattr(reindex_api, "get_component_manager", lambda: manager)
    monkeypatch.setattr(reindex_api, "get_sync_task_service", lambda _manager: Queue())

    response = app.test_client().post("/reindex", json={})

    assert response.status_code == 202
    assert response.get_json()["kind"] == "incremental_reindex"
    assert response.get_json()["status"] == "queued"


def test_deleted_route_is_removed_by_background_task(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    route_manager = RouteManager(str(path))
    route_manager.add_route(make_route(7))
    manager = FakeManager(route_manager)
    service = SyncTaskService(
        manager,
        task_path=str(tmp_path / "sync_tasks.json"),
        sync_service_factory=RecordingSync,
        autostart=False,
        refresh_diagnostics=False,
    )

    route_manager.delete_route(7)
    service.enqueue_routes([7])
    service.process_next()

    assert manager.qdrant_client.deleted == [7]


def test_sync_failure_is_persisted_on_task_and_route(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "SYNC_MAX_ATTEMPTS", 1)
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    route_manager = RouteManager(str(path))
    route_manager.add_route(make_route(1))
    manager = FakeManager(route_manager)
    service = SyncTaskService(
        manager,
        task_path=str(tmp_path / "sync_tasks.json"),
        sync_service_factory=FailingSync,
        autostart=False,
        refresh_diagnostics=False,
    )

    service.enqueue_routes([1])
    service.process_next()

    assert service.list_tasks()[0]["status"] == "error"
    assert route_manager.get_route(1).sync.status == "error"
    assert route_manager.get_route(1).sync.error == "qdrant unavailable"
