import json

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_compare import comparison_detail, comparison_summary
from intent_hub.route_manager import RouteManager
from intent_hub.services.route_service import RouteService
from intent_hub.services.upstream_agent_service import UpstreamAgentService


def upstream_route(route_id, source_id, name, snapshot, overrides=None):
    return RouteConfig(
        id=route_id,
        name=name,
        route_key=f"route.{route_id}",
        description=snapshot["description"],
        utterances=snapshot["utterances"],
        negative_samples=snapshot["negative_samples"],
        source=RouteConfig.RouteSource(
            type="upstream_agent",
            source_id=source_id,
            managed_fields=["name", "description", "utterances", "negative_samples"],
            source_snapshot=snapshot,
            upstream_present=True,
        ),
        sync=RouteConfig.RouteSync(
            status="synced",
            version=1,
            synced_version=1,
            manual_overrides=overrides or [],
        ),
    )


def test_agent_source_deduplicates_labels_and_parses_corpora(monkeypatch):
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://agents.example/api/")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "87,88")
    calls = []

    class Response:
        def __init__(self, data):
            self.data = data

        def raise_for_status(self):
            pass

        def json(self):
            return {"code": 200, "data": self.data}

    class Session:
        def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if url.endswith("/resource/search"):
                return Response({"records": [{"resource": {"id": 9}}]})
            return Response(
                {
                    "id": 9,
                    "title": "Weather",
                    "text": "Forecasts",
                    "extent00": '["today", "today", "tomorrow"]',
                    "extent01": "['sports']",
                }
            )

    agents = AgentSource(Session()).fetch_all()

    assert len(agents) == 1
    assert agents[0]["utterances"] == ["today", "tomorrow"]
    assert agents[0]["negative_samples"] == ["sports"]
    assert len([call for call in calls if call[0].endswith("/detail")]) == 1
    assert all("headers" not in call[1] for call in calls)


def test_pull_preserves_overrides_allocates_local_ids_and_disables_missing(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot_a = {
        "name": "Old A",
        "description": "local description",
        "utterances": ["old"],
        "negative_samples": [],
    }
    snapshot_b = {
        "name": "Old B",
        "description": "B",
        "utterances": ["b"],
        "negative_samples": [],
    }
    route_a = upstream_route(10, "a", "Old A", snapshot_a, ["description"])
    route_a.description = "manual description"
    manager.add_route(route_a)
    manager.add_route(upstream_route(11, "b", "Old B", snapshot_b))

    incoming = [
        {
            "source_id": "a",
            "route_key": "route.10",
            "name": "New A",
            "description": "upstream description",
            "utterances": ["new"],
            "negative_samples": ["not a"],
        },
        {
            "source_id": "c",
            "route_key": "route.c",
            "name": "New A",
            "description": "C",
            "utterances": ["c"],
            "negative_samples": [],
        },
    ]
    components = type("Components", (), {"route_manager": manager})()
    service = UpstreamAgentService(
        components,
        source=type("Source", (), {"fetch_all": lambda self: incoming})(),
    )

    result = service.pull()
    routes = manager.get_all_routes()
    updated_a = next(route for route in routes if route.source.source_id == "a")
    missing_b = next(route for route in routes if route.source.source_id == "b")
    created_c = next(route for route in routes if route.source.source_id == "c")

    assert result["created"] == 1
    assert result["updated"] == 1
    assert result["preserved_overrides"] == 1
    assert result["upstream_missing"] == 1
    assert updated_a.name == "New A"
    assert updated_a.description == "manual description"
    assert updated_a.utterances == ["new"]
    assert missing_b.lifecycle_status == "disabled"
    assert missing_b.source.upstream_present is False
    assert created_c.id == 12
    assert created_c.route_key != updated_a.route_key
    assert set(result["affected_route_ids"]) == {10, 11, 12}
    assert RouteManager(str(path)).get_all_routes()[0].source.source_snapshot


def test_manual_edit_is_tracked_and_can_restore_upstream_field(tmp_path):
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot = {
        "name": "Agent",
        "description": "upstream",
        "utterances": ["one"],
        "negative_samples": [],
    }
    original = upstream_route(3, "source-3", "Agent", snapshot)
    manager.add_route(original)
    components = type("Components", (), {"route_manager": manager})()
    edited = original.model_copy(deep=True)
    edited.description = "manual"

    saved = RouteService(components).update_route(3, edited)

    assert saved.sync.manual_overrides == ["description"]
    assert comparison_summary(saved)["status"] == "local_modified"
    detail = comparison_detail(saved)
    assert detail["fields"]["description"]["local_value"] == "manual"

    restored = UpstreamAgentService(components).restore_fields(3, ["description"])
    assert restored.description == "upstream"
    assert restored.sync.manual_overrides == []
    assert comparison_summary(restored)["status"] == "same"


def test_routes_api_exposes_upstream_summary_and_detail(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    path = tmp_path / "routes.json"
    path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(path))
    snapshot = {
        "name": "Agent",
        "description": "upstream",
        "utterances": ["one"],
        "negative_samples": [],
    }
    manager.add_route(upstream_route(3, "source-3", "Agent", snapshot))
    components = type("Components", (), {"route_manager": manager})()
    monkeypatch.setattr("intent_hub.api.routes.get_component_manager", lambda: components)
    monkeypatch.setattr("intent_hub.api.upstream_agents.get_component_manager", lambda: components)
    client = app.test_client()

    routes_response = client.get("/routes")
    diff_response = client.get("/routes/3/upstream-diff")

    assert routes_response.status_code == 200
    assert routes_response.get_json()[0]["comparison"]["status"] == "same"
    assert diff_response.status_code == 200
    assert diff_response.get_json()["fields"]["utterances"]["unchanged_count"] == 1


# Pulls compare after fetching, inside the write transaction; all fixtures are isolated.
def delta_system(tmp_path):
    from types import SimpleNamespace
    manager = RouteManager(str(tmp_path / "delta.sqlite3"))
    item = dict(source_id="a", route_key="A", name="A", description="original", utterances=["one"], negative_samples=[])
    source = SimpleNamespace(fetch_all=lambda: [item])
    components = SimpleNamespace(route_manager=manager)
    service = UpstreamAgentService(components, source=source)
    service.pull()
    manager.update_sync_state(1, status="synced", synced_version=1)
    with manager.repository.transaction() as db:
        db.execute("DELETE FROM outbox")
    return manager, source, service, item


def test_no_change_pull_has_zero_entity_writes_or_outbox(tmp_path, monkeypatch):
    from unittest.mock import Mock
    manager, source, service, item = delta_system(tmp_path)
    saved = Mock(wraps=manager.repository.save)
    monkeypatch.setattr(manager.repository, "save", saved)
    result = service.pull()
    assert result["unchanged"] == 1
    assert result["affected_route_ids"] == []
    assert manager.repository.pending() == []
    saved.assert_not_called()


def test_override_change_only_saves_baseline(tmp_path):
    manager, source, service, item = delta_system(tmp_path)
    route = manager.get_route(1)
    route.description = "local"
    route.sync.manual_overrides = ["description"]
    manager.repository.save(route, enqueue=False)
    item["description"] = "new upstream"
    result = service.pull()
    route = manager.get_route(1)
    assert result["baseline_updated"] == 1 and result["effective_updated"] == 0
    assert route.description == "local"
    assert route.source.source_snapshot["description"] == "new upstream"
    assert route.sync.version == 1 and manager.repository.pending() == []


def test_edit_during_fetch_is_preserved(tmp_path):
    manager, source, service, item = delta_system(tmp_path)
    def fetch():
        route = manager.get_route(1)
        route.description = "edited during HTTP"
        RouteService(service.components).update_route(1, route)
        return [{**item, "description": "upstream changed", "name": "new name"}]
    source.fetch_all = fetch
    service.pull()
    route = manager.get_route(1)
    assert route.description == "edited during HTTP"
    assert route.name == "new name" and route.sync.version == 3


def test_incomplete_list_and_failed_details_do_not_disable(tmp_path):
    manager, source, service, item = delta_system(tmp_path)
    source.fetch_all = lambda: [{**item, "source_id": "b", "route_key": "B"}]
    source.listed_ids = {"a", "b"}
    source.failed_ids = ["a"]
    result = service.pull()
    assert result["failed"] == 1 and result["upstream_missing"] == 0
    source.listed_ids = {"b"}
    source.complete = False
    result = service.pull()
    assert result["warning"] and result["upstream_missing"] == 0
    assert manager.get_route(1).lifecycle_status == "active"


def test_corpus_order_and_whitespace_do_not_write(tmp_path, monkeypatch):
    from unittest.mock import Mock
    manager, source, service, item = delta_system(tmp_path)
    item["utterances"] = [" one ", "one"]
    item["description"] = "original  "
    saved = Mock(wraps=manager.repository.save)
    monkeypatch.setattr(manager.repository, "save", saved)
    assert service.pull()["unchanged"] == 1
    saved.assert_not_called()


def test_full_list_avoids_details_and_incomplete_total_is_detected(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://example.test")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "1")
    calls = []
    resource = dict(id=1, title="A", text="description", extent00="[]", extent01="[]",
                    attachments=[], author={}, labelsByCategory={}, parameters=[], source={})
    def get(url, **kwargs):
        calls.append(url)
        return SimpleNamespace(raise_for_status=lambda: None,
                               json=lambda: dict(code=200, data=dict(records=[dict(resource=resource)], total=2)))
    source = AgentSource(SimpleNamespace(get=get))
    assert len(source.fetch_all()) == 1
    assert len(calls) == 1 and not source.complete


def test_details_are_bounded_parallel_and_failure_is_reported(monkeypatch):
    import threading
    from types import SimpleNamespace
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://example.test")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "1")
    barrier = threading.Barrier(8)
    active = peak = 0
    lock = threading.Lock()
    def get(url, **kwargs):
        nonlocal active, peak
        if url.endswith("search"):
            data = dict(records=[dict(resource=dict(id=i)) for i in range(8)])
        else:
            with lock:
                active += 1
                peak = max(peak, active)
            barrier.wait(timeout=5)
            with lock:
                active -= 1
            rid = int(url.split("/")[-2])
            if rid == 7:
                raise RuntimeError("unavailable")
            data = dict(id=rid, title="A", text="desc", extent00=[], extent01=[])
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: dict(code=200, data=data))
    source = AgentSource(SimpleNamespace(get=get), workers=8)
    assert len(source.fetch_all()) == 7
    assert peak == 8 and source.failed_ids == ["7"] and source.listed_ids == {str(i) for i in range(8)}


def test_async_pull_endpoint_coalesces_and_persists_task(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from intent_hub.services.sync_task_service import SyncTaskService
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://example.test")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "1")
    components = SimpleNamespace(route_manager=RouteManager(str(tmp_path / "queue.sqlite3")))
    queue = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    monkeypatch.setattr("intent_hub.api.upstream_agents.get_component_manager", lambda: components)
    monkeypatch.setattr("intent_hub.api.upstream_agents.get_sync_task_service", lambda _: queue)
    calls = []
    def fetch(self):
        calls.append(1)
        return []
    monkeypatch.setattr(AgentSource, "fetch_all", fetch)
    client = app.test_client()
    first = client.post("/routes/upstream-pull")
    second = client.post("/routes/upstream-pull")
    assert first.status_code == second.status_code == 202
    assert first.json["id"] == second.json["id"] and calls == []
    assert queue.process_next()
    assert calls == [1] and queue.list_tasks()[0]["status"] == "succeeded"
    restarted = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    assert restarted.list_tasks()[0]["result"]["warning"]


def test_pull_task_creates_index_task_and_source_change_supersedes(tmp_path, monkeypatch):
    from intent_hub.services.sync_task_service import SyncTaskService
    manager, source, service, item = delta_system(tmp_path)
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://example.test")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "1")
    monkeypatch.setattr(AgentSource, "fetch_all", lambda self: [{**item, "description": "changed"}])
    queue = SyncTaskService(service.components, autostart=False, refresh_diagnostics=False)
    task = queue.enqueue_upstream_pull()
    queue.process_next()
    completed = next(t for t in queue.list_tasks() if t["id"] == task["id"])
    assert completed["result"]["effective_updated"] == 1
    assert completed["result"]["sync_task_id"]
    another = queue.enqueue_upstream_pull()
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "2")
    queue._execute_task(queue._find_task(another["id"]))
    assert queue._find_task(another["id"])["status"] == "superseded"


def test_label_scope_change_does_not_disable_previous_scope(tmp_path):
    manager, source, service, item = delta_system(tmp_path)
    source.label_ids = "new-label"
    source.fetch_all = lambda: [{**item, "source_id": "b", "route_key": "B"}]
    assert service.pull()["upstream_missing"] == 0
    assert service.pull()["upstream_missing"] == 0
    assert manager.get_route(1).lifecycle_status == "active"


def test_raw_corpus_order_change_is_noop(tmp_path, monkeypatch):
    from unittest.mock import Mock
    manager, source, service, item = delta_system(tmp_path)
    route = manager.get_route(1)
    item["details"] = dict(title="A", text="original", extent00='["one"]', extent01='[]')
    route.details = item["details"].copy()
    manager.repository.save(route, enqueue=False)
    item["details"]["extent00"] = '["one", "one"]'
    saved = Mock(wraps=manager.repository.save)
    monkeypatch.setattr(manager.repository, "save", saved)
    assert service.pull()["unchanged"] == 1
    saved.assert_not_called()


def test_source_reads_verified_pagination_and_preserves_extra_details(monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://example.test")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "1")
    pages = []
    def get(url, params=None, **kwargs):
        if url.endswith('search'):
            page = params.get('pageNum', 1)
            pages.append(page)
            data = dict(total=2, pageNum=page, pageSize=1, records=[dict(resource=dict(
                id=page, title='A', text='desc', extent00=[], extent01=[]))])
        else:
            data = dict(id=int(url.split('/')[-2]), title='A', text='desc', extent00=[], extent01=[],
                        parameters=[{'name': 'kept'}], source='original')
        return SimpleNamespace(raise_for_status=lambda: None, json=lambda: dict(code=200, data=data))
    source = AgentSource(SimpleNamespace(get=get))
    agents = source.fetch_all()
    assert pages == [1, 2] and source.complete and len(agents) == 2
    assert all(a['details']['parameters'] == [{'name': 'kept'}] for a in agents)


def test_restarted_pull_reconnects_pending_index_work(tmp_path, monkeypatch):
    from intent_hub.services.sync_task_service import SyncTaskService
    manager, source, service, item = delta_system(tmp_path)
    monkeypatch.setattr(Config, 'AGENT_API_URL', 'https://example.test')
    monkeypatch.setattr(Config, 'AGENT_API_LABEL_IDS', '1')
    route = manager.get_route(1)
    route.sync.version = 2
    route.sync.status = 'pending'
    manager.repository.save(route)
    monkeypatch.setattr(AgentSource, 'fetch_all', lambda self: [item])
    queue = SyncTaskService(service.components, autostart=False, refresh_diagnostics=False)
    task = queue.enqueue_upstream_pull()
    queue._find_task(task['id'])['status'] = 'running'
    queue._save_tasks()
    restarted = SyncTaskService(service.components, autostart=False, refresh_diagnostics=False)
    recovered = restarted._find_task(task['id'])
    assert recovered['status'] == 'queued'
    restarted._execute_task(recovered)
    assert recovered['result']['unchanged'] == 1
    assert recovered['result']['sync_task_id']
    index = restarted._find_task(recovered['result']['sync_task_id'])
    assert index['route_versions']['1'] == 2


def test_route_key_matches_import_regardless_of_source_id(tmp_path):
    from types import SimpleNamespace
    manager = RouteManager(str(tmp_path / 'identity.sqlite3'))
    route = RouteConfig(id=103, name='Original', route_key='shared.key', description='old', utterances=['old'],
        source=RouteConfig.RouteSource(type='json_import', source_id='collection'),
        sync=RouteConfig.RouteSync(version=1, synced_version=1, status='synced', manual_overrides=['utterances']))
    manager.repository.save(route, enqueue=False)
    item = dict(source_id='new-source-id', route_key='shared.key', name='New name', description='new', utterances=['new'], negative_samples=[])
    service = UpstreamAgentService(SimpleNamespace(route_manager=manager), source=SimpleNamespace(fetch_all=lambda: [item]))
    assert service.pull()['created'] == 0
    assert len(manager.get_all_routes()) == 1
    assert manager.get_route(103).description == 'new'
    assert manager.get_route(103).utterances == ['old']
    item['source_id'] = 'changed-again'
    assert service.pull()['created'] == 0
    assert service.pull()['unchanged'] == 1


def test_different_route_keys_do_not_merge_even_with_same_source_id(tmp_path):
    manager, source, service, item = delta_system(tmp_path)
    item['route_key'] = 'different.key'
    assert service.pull()['created'] == 1
    assert {r.route_key for r in manager.get_all_routes()} == {'a', 'different.key'}


def test_duplicate_incoming_route_keys_abort_without_writes(tmp_path):
    import pytest
    manager, source, service, item = delta_system(tmp_path)
    source.fetch_all = lambda: [item, {**item, 'source_id': 'another'}]
    with pytest.raises(ValueError, match='路由标识重复'):
        service.pull()
    assert len(manager.get_all_routes()) == 1
    assert manager.repository.pending() == []
