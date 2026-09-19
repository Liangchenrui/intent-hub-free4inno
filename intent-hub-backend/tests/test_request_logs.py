import pytest

from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import PredictResponse
from intent_hub.services.log_service import LogStore, get_log_store


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(Config, "API_COMPAT_PROFILE", "bupt")
    monkeypatch.setattr(Config, "AUTH_CODE", "test-management-key")
    monkeypatch.setattr(Config, "PREDICT_AUTH_KEY", "test-route-key")
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    class Components:
        def ensure_ready(self):
            pass
    monkeypatch.setattr("intent_hub.api.prediction.get_component_manager", Components)
    monkeypatch.setattr("intent_hub.api.prediction.PredictionService.predict", lambda *args: [
        PredictResponse(id=7, name="example", route_key="example", score=0.91)])
    return app.test_client()


def test_request_roundtrip_auth_and_persistence(client):
    text = "  完整输入\n第二行  "
    response = client.post("/predict", json={"text": text},
                           headers={"Authorization": "Bearer test-route-key"})
    assert response.status_code == 200
    rid = response.headers["X-Request-ID"]
    assert client.get("/logs/routing").status_code == 401
    assert client.get("/logs/routing", headers={"X-API-Key": "test-route-key"}).status_code == 401
    headers = {"X-API-Key": "test-management-key"}
    data = client.get(f"/logs/routing?request_id={rid}", headers=headers).get_json()
    assert data["total"] == 1
    assert data["items"][0]["input_text"] == text
    assert data["items"][0]["result"] == response.get_json()
    runtime = client.get(f"/logs/runtime?request_id={rid}", headers=headers).get_json()
    assert runtime["total"] == 1
    assert runtime["items"][0]["status_code"] == 200
    reopened = LogStore(get_log_store().path)
    assert reopened.query("routing", rid)["total"] == 1
    assert b"test-route-key" not in get_log_store().path.read_bytes()
    assert client.get("/logs/routing?page_size=101", headers=headers).status_code == 400
    assert client.get("/logs/routing?page=oops", headers=headers).status_code == 400


@pytest.mark.parametrize("path", ["/route", "/compat/bupt/route"])
def test_bupt_full_input_and_one_record(client, monkeypatch, path):
    monkeypatch.setattr("intent_hub.compat_api.get_component_manager", lambda: None)
    monkeypatch.setattr("intent_hub.compat_api.PredictionService.route", lambda *args: {"matched": False})
    response = client.post(path, json={"query": "  原文  "},
                           headers={"X-API-Key": "test-management-key"})
    assert response.status_code == 200
    data = get_log_store().query("routing", response.headers["X-Request-ID"])
    assert data["total"] == 1
    assert data["items"][0]["input_text"] == "  原文  "


def test_storage_failure_does_not_fail_prediction(client, monkeypatch):
    def unavailable(*args):
        raise OSError("disk unavailable")
    monkeypatch.setattr(LogStore, "connect", unavailable)
    response = client.post("/predict", json={"text": "hello"},
                           headers={"X-API-Key": "test-route-key"})
    assert response.status_code == 200
    assert response.get_json()[0]["id"] == 7
    assert client.get("/logs/runtime", headers={"X-API-Key": "test-management-key"}).status_code == 503


def test_master_management_auth(client, monkeypatch):
    monkeypatch.setattr(Config, "API_COMPAT_PROFILE", "master")
    monkeypatch.setattr(Config, "AUTH_ENABLED", True)
    class Auth:
        def is_valid(self, key):
            return key == "management-session"
    monkeypatch.setattr("intent_hub.auth.get_auth_manager", Auth)
    assert client.get("/logs/runtime").status_code == 401
    assert client.get("/logs/runtime", headers={"X-API-Key": "management-session"}).status_code == 200


def test_failed_route_record(client, monkeypatch):
    def fail(*args):
        from intent_hub.utils.route_trace import trace_event
        trace_event("encoding")
        raise RuntimeError("simulated")
    monkeypatch.setattr("intent_hub.compat_api.get_component_manager", lambda: None)
    monkeypatch.setattr("intent_hub.compat_api.PredictionService.route", fail)
    response = client.post("/route", json={"query": "failure input"},
                           headers={"X-API-Key": "test-management-key"})
    assert response.status_code == 500
    rid = response.headers["X-Request-ID"]
    record = get_log_store().query("routing", rid)["items"][0]
    assert record["status"] == "failed"
    assert record["result"] is None
    assert record["events"][0]["stage"] == "encoding"
    assert record["events"][0]["offset_ms"] >= 0
    assert get_log_store().query("runtime", rid)["items"][0]["level"] == "ERROR"
    logs = get_log_store().query("runtime", rid)["items"]
    assert any("RuntimeError: simulated" in (item.get("exception") or "") for item in logs)


def test_runtime_background_redaction_and_handler_failure(client, monkeypatch):
    from intent_hub.utils.logger import logger
    logger.info("background test-route-key")
    item = get_log_store().query("runtime")["items"][0]
    assert item["request_id"] == ""
    assert item["message"] == "background [REDACTED]"
    with app.test_request_context(headers={"Authorization": "Bearer transient-secret"}):
        try:
            raise ValueError("transient-secret")
        except ValueError:
            logger.exception("provider failed transient-secret")
    item = get_log_store().query("runtime")["items"][0]
    assert "transient-secret" not in str(item)
    assert "ValueError: [REDACTED]" in item["exception"]
    monkeypatch.setattr(LogStore, "append", lambda *args: (_ for _ in ()).throw(OSError()))
    logger.error("still returns without recursion")


def test_expired_records_hidden_and_pagination(client, monkeypatch):
    monkeypatch.setattr("intent_hub.services.log_service.time.time", lambda: 4_000_000)
    cutoff = 4_000_000 - 30 * 86400
    store = get_log_store()
    store.append([("routing", cutoff - 1, "old", {}),
                  ("routing", cutoff, "boundary", {}),
                  ("routing", cutoff + 1, "new", {})])
    data = store.query("routing", page=2, page_size=1)
    assert data["total"] == 2
    assert data["items"][0]["request_id"] == "boundary"


def test_filters_and_master_compat_auth(client, monkeypatch):
    import time
    now = time.time()
    store = get_log_store()
    store.append([("runtime", now, "filter-target", {"level": "ERROR", "message": "literal %_ 中文"}),
                  ("runtime", now - 100, "older", {"level": "INFO", "message": "other"}),
                  ("routing", now, "filter-target", {"input_text": "原文 %_"})])
    headers = {"X-API-Key": "test-management-key"}
    result = client.get('/logs/runtime', query_string={"keyword": "%_", "level": "ERROR", "start": now - 1, "end": now + 1}, headers=headers)
    assert result.status_code == 200
    assert result.json["total"] == 1
    assert result.json["items"][0]["request_id"] == "filter-target"
    assert store.query("routing", keyword="原文")["total"] == 1
    assert store.query("runtime", keyword="' OR 1=1 --")["total"] == 0
    for params in ({"start": "nan"}, {"end": "inf"}, {"start": 2, "end": 1}, {"level": "INVALID"}):
        assert client.get('/logs/runtime', query_string=params, headers=headers).status_code == 400
    monkeypatch.setattr(Config, "AUTH_ENABLED", True)
    class Auth:
        def is_valid(self, key):
            return key == 'master-session'
    monkeypatch.setattr('intent_hub.auth.get_auth_manager', Auth)
    assert client.get('/compat/master/logs/runtime', headers={'X-API-Key': 'master-session'}).status_code == 200
    assert client.get('/compat/master/logs/runtime', headers=headers).status_code == 401


def test_stage_durations_and_failure_persist(client, monkeypatch):
    from flask import g
    from intent_hub.utils.route_trace import trace_event, trace_stage
    clock = [100.0]
    monkeypatch.setattr('intent_hub.utils.route_trace.monotonic', lambda: clock[0])

    def fail(*args):
        g.log_started = 100.0
        with trace_stage('preparing'):
            clock[0] += 0.025
        trace_event('encoding')
        with trace_stage('encoding'):
            clock[0] += 0.125
            raise RuntimeError('failure')

    monkeypatch.setattr('intent_hub.compat_api.get_component_manager', lambda: None)
    monkeypatch.setattr('intent_hub.compat_api.PredictionService.route', fail)
    response = client.post('/route', json={'query': 'timed'}, headers={'X-API-Key': 'test-management-key'})
    record = get_log_store().query('routing', response.headers['X-Request-ID'])['items'][0]
    assert record['category'] == 'routing'
    assert record['events'][0]['offset_ms'] == 25
    assert record['timings'] == [
        {'stage': 'preparing', 'offset_ms': 0, 'status': 'succeeded', 'elapsed_ms': 25},
        {'stage': 'encoding', 'offset_ms': 25, 'status': 'failed', 'elapsed_ms': 125, 'error_type': 'RuntimeError'},
    ]


def test_category_filter_before_pagination_and_legacy(client):
    import time
    now = time.time()
    store = get_log_store()
    store.append([
        ('runtime', now, 's1', {'category': 'sync', 'message': 'one'}),
        ('runtime', now + 1, 'r1', {'category': 'routing', 'message': 'two'}),
        ('runtime', now + 2, 's2', {'message': 'Route sync id=7'}),
        ('runtime', now + 3, 'r2', {'path': '/compat/master/predict'}),
        ('runtime', now + 4, 'unknown', {'message': 'old background event'}),
    ])
    headers = {'X-API-Key': 'test-management-key'}
    response = client.get('/logs/runtime', query_string={'category': 'sync', 'page_size': 1, 'page': 2}, headers=headers)
    assert response.status_code == 200
    assert response.json['total'] == 2
    assert response.json['items'][0]['request_id'] == 's1'
    assert response.json['items'][0]['category_inferred'] is False
    legacy = store.query('runtime', 's2')['items'][0]
    assert legacy['category'] == 'sync' and legacy['category_inferred'] is True
    assert store.query('runtime', 'r2', category='routing')['total'] == 1
    assert store.query('runtime', 'unknown')['items'][0]['category'] == 'system'
    assert client.get('/logs/runtime?category=invalid', headers=headers).status_code == 400


def test_background_scope_isolated_from_requests(client):
    from concurrent.futures import ThreadPoolExecutor
    from intent_hub.utils.log_context import log_scope
    from intent_hub.utils.logger import logger

    def background():
        with log_scope('sync'):
            logger.info('scoped background', extra={'task_id': 'task-7', 'elapsed_ms': 12.5})
        logger.info('scope reset')

    with ThreadPoolExecutor(max_workers=1) as pool:
        pool.submit(background).result()
    store = get_log_store()
    item = store.query('runtime', keyword='scoped background')['items'][0]
    assert item['category'] == 'sync' and item['task_id'] == 'task-7'
    assert item['elapsed_ms'] == 12.5 and item['request_id'] == ''
    assert store.query('runtime', keyword='scope reset')['items'][0]['category'] == 'system'
    response = client.post('/predict', json={'text': 'hello'}, headers={'X-API-Key': 'test-route-key'})
    assert store.query('runtime', response.headers['X-Request-ID'])['items'][0]['category'] == 'routing'
