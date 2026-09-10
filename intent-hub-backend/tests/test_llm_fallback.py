"""Offline behavior/contract tests. These do not measure real model accuracy."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from intent_hub.config import Config
from intent_hub.intent_description import description_text
from intent_hub.models import PredictRequest, RouteConfig
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.services.fallback_service import FallbackDecision, FallbackService, LLMFactory
from intent_hub.services.prediction_service import PredictionService
from intent_hub.services.sync_service import SyncService
from intent_hub.services.sync_task_service import SyncTaskService


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "LLM_FALLBACK_ENABLED", True)
    monkeypatch.setattr(Config, "LLM_FALLBACK_TOP_K", 5)
    monkeypatch.setattr(Config, "LLM_FALLBACK_TIMEOUT_SECONDS", 1)
    monkeypatch.setattr(Config, "EMBEDDING_MODEL_NAME", "offline-test")
    route_manager = RouteManager(str(tmp_path / "routes.json"))
    client = object.__new__(IntentHubQdrantClient)
    client.collection_name = "test"
    client.dimensions = 2
    client.write_batch_size = 32
    client.client = QdrantClient(":memory:")
    client.client.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))

    class Encoder:
        calls = []

        def encode_single(self, text):
            self.calls.append(text)
            return [1.0, 0.0]

        def encode(self, texts):
            return [[0.0, 1.0] for _ in texts]

    manager = SimpleNamespace(
        route_manager=route_manager, qdrant_client=client, encoder=Encoder(), ensure_ready=lambda: None,
    )
    route = RouteConfig(
        id=1, name="查询订单", route_key="orders.track",
        description="查询订单状态和物流，不支持取消订单或修改地址。",
        utterances=["订单在哪里"], negative_samples=["取消订单"],
        sync=RouteConfig.RouteSync(status="pending", version=1),
    )
    route_manager.add_route(route)
    SyncService(manager).sync_route(1)
    yield manager
    client.client.close()


def set_model(monkeypatch, output, calls=None):
    class Model:
        async def ainvoke(self, messages):
            if calls is not None:
                calls.append(messages)
            if isinstance(output, Exception):
                raise output
            return AIMessage(content=output)

    monkeypatch.setattr(LLMFactory, "create_llm", lambda **kwargs: Model())


def test_unmatched_retrieves_definitions_and_returns_validated_entity(system, monkeypatch):
    calls = []
    set_model(monkeypatch, '{"status":"matched","route_id":1}', calls)
    result = PredictionService(system).predict(PredictRequest(text="包裹现在到哪了"))[0]
    assert (result.id, result.route_key, result.score) == (1, "orders.track", None)
    assert (result.match_source, result.fallback_status) == ("llm_fallback", "matched")
    data = json.loads(calls[0][1].content)
    assert data["candidates"][0]["description"].endswith("不支持取消订单或修改地址。")
    assert data["candidates"][0]["negative_samples"] == ["取消订单"]
    # Query embedding is reused, rather than requesting a second embedding for fallback.
    assert system.encoder.calls.count("包裹现在到哪了") == 1


def test_empty_utterance_search_also_uses_fallback(system, monkeypatch):
    monkeypatch.setattr(system.qdrant_client, "search", lambda *a, **kw: [])
    set_model(monkeypatch, '{"status":"matched","route_id":1}')
    assert PredictionService(system).predict(PredictRequest(text="配送进度"))[0].match_source == "llm_fallback"


@pytest.mark.parametrize("enabled,score,expected", [(False, 0.1, "default"), (True, 0.99, "semantic")])
def test_disabled_or_existing_match_never_calls_llm(system, monkeypatch, enabled, score, expected):
    monkeypatch.setattr(Config, "LLM_FALLBACK_ENABLED", enabled)
    monkeypatch.setattr(system.qdrant_client, "search", lambda *a, **kw: [
        {"score": score, "payload": {"route_id": 1, "route_name": "查询订单"}}
    ])
    def fail(*a, **kw):
        pytest.fail("fallback must not run")
    monkeypatch.setattr(LLMFactory, "create_llm", fail)
    assert PredictionService(system).predict(PredictRequest(text="query"))[0].match_source == expected


@pytest.mark.parametrize("output,status", [
    ('{"status":"no_match","route_id":null}', "no_match"),
    ('{"status":"ambiguous","route_id":null}', "ambiguous"),
    ('{"status":"matched","route_id":999}', "unavailable"),
    ('{"status":"matched","route_id":"1"}', "unavailable"),
    ('{"status":"matched","route_id":true}', "unavailable"),
    ('{"status":"matched","route_id":null}', "unavailable"),
    ('{"status":"no_match","route_id":1}', "unavailable"),
    ('{"status":"matched","route_id":1,"confidence":0.99}', "unavailable"),
    ('{"status":"matched","route_id":1', "unavailable"),
    (RuntimeError("provider unavailable"), "unavailable"),
])
def test_abstention_and_invalid_outputs_keep_default(system, monkeypatch, output, status):
    set_model(monkeypatch, output)
    result = PredictionService(system).predict(PredictRequest(text="修改收货地址"))[0]
    assert result.id == Config.DEFAULT_ROUTE_ID
    assert result.match_source == "default"
    assert result.fallback_status == status


@pytest.mark.parametrize("change", ["excluded", "inactive", "deleted", "stale", "legacy"])
def test_ineligible_candidates_never_reach_model(system, monkeypatch, change):
    route = system.route_manager.get_route(1)
    excluded = set()
    if change == "excluded":
        excluded.add(1)
    elif change == "inactive":
        route.lifecycle_status = "disabled"
        system.route_manager.update_route(1, route)
    elif change == "deleted":
        system.route_manager.delete_route(1)
    elif change == "stale":
        route.description = "新职责"
        system.route_manager.update_route(1, route)
    else:
        system.qdrant_client.upsert_route_metadata(route)
    def fail(*a, **kw):
        pytest.fail("no eligible candidate should reach the model")
    monkeypatch.setattr(LLMFactory, "create_llm", fail)
    result = FallbackService(system).predict("query", [1.0, 0.0], excluded)
    assert result.fallback_status == "no_candidates"


def test_negative_exclusion_survives_fallback(system, monkeypatch):
    monkeypatch.setattr(system.qdrant_client, "search_negative_samples", lambda *a, **kw: [
        {"score": 0.99, "payload": {"route_id": 1, "negative_threshold": 0.9}}
    ])
    set_model(monkeypatch, '{"status":"matched","route_id":1}')
    result = PredictionService(system).predict(PredictRequest(text="取消订单"))[0]
    assert result.fallback_status == "no_candidates"


def test_route_changed_during_model_call_is_not_returned(system, monkeypatch):
    def classify(*args):
        system.route_manager.delete_route(1)
        return FallbackDecision(status="matched", route_id=1)
    monkeypatch.setattr(FallbackService, "_classify", staticmethod(classify))
    assert FallbackService(system).predict("query", [1.0, 0.0], set()).fallback_status == "no_candidates"


def test_in_place_edit_during_model_call_uses_immutable_candidate_snapshot(system, monkeypatch):
    def classify(*args):
        route = system.route_manager.get_route(1)
        route.description = "Changed while model was running"
        system.route_manager.update_route(1, route)
        return FallbackDecision(status="matched", route_id=1)
    monkeypatch.setattr(FallbackService, "_classify", staticmethod(classify))
    assert FallbackService(system).predict("query", [1.0, 0.0], set()).fallback_status == "no_candidates"


def test_version_change_during_embedding_is_not_acknowledged(system, monkeypatch):
    route = system.route_manager.get_route(1)
    route.sync.status = "pending"
    system.qdrant_client.upsert_route_metadata(route)
    def encode(text):
        system.route_manager.update_sync_state(1, version=2, status="pending")
        return [1.0, 0.0]
    monkeypatch.setattr(system.encoder, "encode_single", encode)
    SyncService(system)._sync_metadata(route)
    current = system.route_manager.get_route(1)
    assert current.sync.status == "pending" and current.sync.synced_version == 1


def test_model_deadline_cancels_request_and_preserves_default(system, monkeypatch):
    cancelled = []
    options = []
    class SlowModel:
        async def ainvoke(self, messages):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.append(True)
    def create(**kwargs):
        options.append(kwargs)
        return SlowModel()
    monkeypatch.setattr(LLMFactory, "create_llm", create)
    result = FallbackService(system).predict("query", [1.0, 0.0], set())
    assert result.fallback_status == "unavailable"
    assert cancelled == [True]
    assert options[0].pop("http_async_client").is_closed
    assert options == [{"temperature": 0, "timeout": 1, "max_retries": 0}]


def test_description_sync_backfills_legacy_and_reuses_unchanged_vectors(system):
    route = system.route_manager.get_route(1)
    system.qdrant_client.upsert_route_metadata(route)
    system.encoder.calls.clear()
    service = SyncService(system)
    service._sync_metadata(route)
    service._sync_metadata(route)
    assert system.encoder.calls == [description_text(route)]
    assert system.qdrant_client.get_description_embedding(route, Config.EMBEDDING_MODEL_NAME) == [1.0, 0.0]
    assert system.qdrant_client.get_description_embedding(route, "other-model") is None
    route.description = "另一个职责"
    assert system.qdrant_client.get_description_embedding(route, Config.EMBEDDING_MODEL_NAME) is None
    # The metadata point is not mixed with utterances or negative examples.
    hits = system.qdrant_client.search([1.0, 0.0], 5)
    assert len(hits) == 1 and hits[0]["score"] == 0


def test_metadata_write_failure_does_not_acknowledge_sync(system, monkeypatch):
    route = system.route_manager.get_route(1)
    route.sync.status = "pending"
    route.sync.version = 2
    system.route_manager.update_route(1, route)
    def fail(**kw):
        raise RuntimeError("write failed")
    monkeypatch.setattr(system.qdrant_client, "upsert_route_metadata", fail)
    with pytest.raises(RuntimeError, match="write failed"):
        SyncService(system)._sync_metadata(route)
    current = system.route_manager.get_route(1)
    assert current.sync.status == "pending" and current.sync.synced_version == 1


def test_description_lookup_filters_exclusions_before_top_k(system):
    route = system.route_manager.get_route(1).model_copy(update={"id": 2, "route_key": "second"})
    system.qdrant_client.upsert_route_metadata(route, model_name=Config.EMBEDDING_MODEL_NAME, embedding=[0.8, 0.6])
    hits = system.qdrant_client.search_route_descriptions([1.0, 0.0], route_ids=[2], top_k=1)
    assert [hit["payload"]["route_id"] for hit in hits] == [2]


def test_background_task_preserves_description_vector(system, tmp_path):
    queue = SyncTaskService(
        system, task_path=str(tmp_path / "tasks.json"), autostart=False, refresh_diagnostics=False
    )
    task = queue.enqueue_routes([1])
    assert queue.process_next()
    assert queue.list_tasks()[0]["status"] == "succeeded"
    route = system.route_manager.get_route(1)
    assert route.sync.task_id == task["id"]
    assert system.qdrant_client.get_description_embedding(route, Config.EMBEDDING_MODEL_NAME) == [1.0, 0.0]
    hits = system.qdrant_client.search_route_descriptions([1.0, 0.0], [1])
    assert hits[0]["payload"]["route_config"]["sync"]["task_id"] == task["id"]


def test_http_predict_returns_fallback_contract_and_requires_auth(system, monkeypatch):
    from intent_hub.app import app

    monkeypatch.setattr(Config, "PREDICT_AUTH_KEY", "offline-route-key")
    monkeypatch.setattr("intent_hub.api.prediction.get_component_manager", lambda: system)
    set_model(monkeypatch, '{"status":"matched","route_id":1}')
    client = app.test_client()
    assert client.post("/predict", json={"text": "包裹现在到哪了"}).status_code == 401
    response = client.post(
        "/predict", json={"text": "包裹现在到哪了"},
        headers={"Authorization": "Bearer offline-route-key"},
    )
    assert response.status_code == 200
    assert response.get_json() == [{
        "id": 1, "name": "查询订单", "route_key": "orders.track", "score": None,
        "match_source": "llm_fallback", "fallback_status": "matched",
    }]


def test_settings_api_saves_fallback_controls_and_rejects_bad_values(tmp_path, monkeypatch):
    from intent_hub.app import app

    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    monkeypatch.setattr(Config, "SETTINGS_FILE_PATH", str(tmp_path / "settings.json"))
    for key in ("LLM_FALLBACK_ENABLED", "LLM_FALLBACK_TOP_K", "LLM_FALLBACK_TIMEOUT_SECONDS"):
        monkeypatch.setattr(Config, key, getattr(Config, key))
    resets = []
    monkeypatch.setattr("intent_hub.core.components.get_component_manager", lambda: SimpleNamespace(
        reset_components=lambda: resets.append(True)
    ))
    client = app.test_client()
    response = client.post("/settings", json={
        "LLM_FALLBACK_ENABLED": True, "LLM_FALLBACK_TOP_K": 3, "LLM_FALLBACK_TIMEOUT_SECONDS": 4,
    })
    assert response.status_code == 200 and resets == [True]
    assert json.loads((tmp_path / "settings.json").read_text())["LLM_FALLBACK_TOP_K"] == 3
    assert client.get("/settings").get_json()["LLM_FALLBACK_ENABLED"] is True
    assert client.post("/settings", json={"LLM_FALLBACK_TOP_K": -1}).status_code == 400
    assert Config.LLM_FALLBACK_TOP_K == 3 and resets == [True]


@pytest.mark.parametrize("values", [
    {"LLM_FALLBACK_ENABLED": "false"}, {"LLM_FALLBACK_TOP_K": 0},
    {"LLM_FALLBACK_TOP_K": 21}, {"LLM_FALLBACK_TOP_K": True},
    {"LLM_FALLBACK_TIMEOUT_SECONDS": 0}, {"LLM_FALLBACK_TIMEOUT_SECONDS": float("nan")},
])
def test_invalid_settings_rejected_before_any_mutation(tmp_path, monkeypatch, values):
    path = tmp_path / "settings.json"
    path.write_text('{}', encoding="utf-8")
    monkeypatch.setattr(Config, "SETTINGS_FILE_PATH", str(path))
    before = Config.to_dict()
    with pytest.raises(ValueError):
        Config.save(values)
    assert path.read_text() == '{}'
    assert Config.to_dict() == before


def test_consecutive_real_sdk_calls_work_across_request_event_loops(monkeypatch):
    """Use an actual local HTTP transport to catch cached-client/closed-loop failures."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *_args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({
                "id": "local-test", "object": "chat.completion", "created": 0,
                "model": "local-test", "choices": [{"index": 0, "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"status":"matched","route_id":1}'}}],
            }).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setattr(Config, "LLM_PROVIDER", "deepseek")
    monkeypatch.setattr(Config, "LLM_API_KEY", "local-test-key")
    monkeypatch.setattr(Config, "LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}/v1")
    monkeypatch.setattr(Config, "LLM_MODEL", "local-test")
    monkeypatch.setattr(Config, "LLM_FALLBACK_TIMEOUT_SECONDS", 5)
    try:
        for _ in range(3):
            decision = FallbackService._classify("query", [{"route_id": 1, "name": "test"}])
            assert decision.route_id == 1 and decision.status == "matched"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
