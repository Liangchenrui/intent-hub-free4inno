"""BUPT fallback contract tests; local transports do not measure model accuracy."""

import asyncio
import json
import uuid
from types import SimpleNamespace

import httpx
import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from intent_hub.agent_store import AgentStore
from intent_hub.config import Config
from intent_hub.intent_description import description_text
from intent_hub.models import Agent
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.services.fallback_service import FallbackService
from intent_hub.services.prediction_service import PredictionService
from intent_hub.services.sync_service import SyncService, agent_hash


@pytest.fixture
def system(tmp_path, monkeypatch):
    for key, value in {
        "LLM_FALLBACK_ENABLED": True, "LLM_FALLBACK_TOP_K": 5,
        "LLM_FALLBACK_TIMEOUT_SECONDS": 1, "LLM_PROVIDER": "deepseek",
        "LLM_API_KEY": "local-test-key", "LLM_BASE_URL": "https://llm.invalid/v1",
        "LLM_MODEL": "test-model", "EMBEDDING_MODEL_NAME": "offline-test",
        "QDRANT_COLLECTION": "test", "MAX_DELETE_RATIO": 1,
        "DEFAULT_ROUTE_FILE": tmp_path / "default.txt",
    }.items():
        monkeypatch.setattr(Config, key, value)
    Config.DEFAULT_ROUTE_FILE.write_text("默认处理", encoding="utf-8")
    store = AgentStore(tmp_path / "agents.db")
    store.upsert(Agent(id=1, title="查询订单", text="查询订单状态和物流，不支持取消或退款。",
                       utterances=["订单到哪里了"], negative_samples=["取消订单"],
                       details={"id": 1, "title": "查询订单", "extra": "upstream-field"}))
    client = object.__new__(IntentHubQdrantClient)
    client.collection_name = "test"
    client.dimensions = 2
    client.client = QdrantClient(":memory:")
    client.client.create_collection("test", vectors_config=VectorParams(size=2, distance=Distance.COSINE))

    class Encoder:
        calls = []

        def encode(self, texts):
            self.calls.extend(texts)
            return [[1.0, 0.0] if text.startswith("名称：") else [0.0, 1.0] for text in texts]

        def encode_single(self, query):
            self.calls.append(query)
            return [1.0, 0.0]

    manager = SimpleNamespace(agent_store=store, qdrant_client=client, encoder=Encoder())
    manager.sync = SyncService(manager, state_path=tmp_path / "sync.db")
    manager.sync.sync()
    yield manager
    client.client.close()


@pytest.fixture
def model(monkeypatch):
    original = httpx.AsyncClient
    state = SimpleNamespace(calls=[], content='{"status":"matched","route_id":1}', delay=0, status=200)

    async def handler(request):
        state.calls.append(request)
        if state.delay:
            await asyncio.sleep(state.delay)
        return httpx.Response(state.status, json={"choices": [{"message": {"content": state.content}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    return state


def test_unmatched_reuses_query_and_returns_upstream_details(system, model):
    result = PredictionService(system).route("包裹走到哪了")
    assert result["matched"] is True
    assert result["match_source"] == "llm_fallback" and result["fallback_status"] == "matched"
    assert result["agents"] == [{"agent": system.agent_store.get(1).details, "score": None}]
    assert system.encoder.calls.count("包裹走到哪了") == 1
    body = json.loads(model.calls[0].content)
    assert body["temperature"] == 0
    assert body["messages"][0]["role"] == "system"
    data = json.loads(body["messages"][1]["content"])
    assert data["candidates"][0]["negative_samples"] == ["取消订单"]


@pytest.mark.parametrize("content, expected", [
    ('{"status":"no_match","route_id":null}', "no_match"),
    ('{"status":"ambiguous","route_id":null}', "ambiguous"),
    ('{"status":"matched","route_id":999}', "unavailable"),
    ('{"status":"matched","route_id":"1"}', "unavailable"),
    ('{"status":"matched","route_id":true}', "unavailable"),
    ('{"status":"matched","route_id":null}', "unavailable"),
    ('{"status":"no_match","route_id":1}', "unavailable"),
    ('{"status":"matched","route_id":1,"confidence":0.99}', "unavailable"),
    ('{"status":"matched"', "unavailable"),
])
def test_abstention_and_invalid_outputs_preserve_default(system, model, content, expected):
    model.content = content
    result = PredictionService(system).route("查询")
    assert result == {"matched": False, "agents": [], "text": "默认处理",
                      "match_source": "default", "fallback_status": expected}


@pytest.mark.parametrize("enabled, score, expected", [(False, 0.1, "default"), (True, 0.99, "semantic")])
def test_disabled_or_existing_match_does_not_call_model(system, model, monkeypatch, enabled, score, expected):
    monkeypatch.setattr(Config, "LLM_FALLBACK_ENABLED", enabled)
    monkeypatch.setattr(system.qdrant_client, "search", lambda *a, **kw: [{"score": score, "payload": {"route_id": 1}}])
    result = PredictionService(system).route("查询")
    assert result["match_source"] == expected and not model.calls


@pytest.mark.parametrize("change", ["negative", "inactive", "deleted", "stale", "legacy"])
def test_ineligible_agents_never_reach_model(system, model, monkeypatch, change):
    if change == "negative":
        monkeypatch.setattr(system.qdrant_client, "search_negative_samples", lambda *a, **kw: [
            {"score": 0.99, "payload": {"route_id": 1}}])
    elif change in {"inactive", "deleted"}:
        system.agent_store.update(1, {"lifecycle_status": change})
    elif change == "stale":
        system.agent_store.update(1, {"text": "已变更的职责"})
    else:
        system.qdrant_client.client.delete_payload(
            "test", keys=["description_hash"], points=[str(uuid.uuid5(uuid.NAMESPACE_DNS, "route-metadata:1"))])
    result = PredictionService(system).route("查询")
    assert result["fallback_status"] == "no_candidates" and not model.calls


def test_metadata_is_excluded_from_corpus_and_filters_before_top_k(system):
    client = system.qdrant_client
    assert client.search([1.0, 0.0])[0]["score"] == 0
    assert len(client.get_route_vectors(1)) == 2
    assert len(client.scroll_all_points()) == 2
    assert len(client.scroll_all_points(exclude_negative=True)) == 1
    assert client.search_route_descriptions([1.0, 0.0], route_ids=[2], top_k=1) == []
    agent = system.agent_store.get(1).model_copy(update={"id": 2, "upstream_id": 2, "title": "另一职责"})
    system.agent_store.upsert(agent)
    system.sync.sync()
    assert client.search_route_descriptions([1.0, 0.0], route_ids=[2], top_k=1)[0]["payload"]["route_id"] == 2


def test_sync_backfills_missing_metadata_and_reuses_unchanged_description(system):
    before = list(system.encoder.calls)
    assert system.sync.sync()["changed_agents"] == 0
    assert system.encoder.calls == before
    system.agent_store.update(1, {"utterances": ["新增语料"]})
    description = description_text(system.agent_store.get(1))
    system.sync.sync()
    assert system.encoder.calls.count(description) == 1
    system.qdrant_client.client.delete("test", points_selector=[str(uuid.uuid5(uuid.NAMESPACE_DNS, "route-metadata:1"))])
    assert system.sync.status()["synced"] is False
    assert system.sync.sync()["changed_agents"] == 1
    assert system.sync.status()["synced"] is True


def test_description_only_agent_can_be_synced_and_routed(system, model):
    system.agent_store.update(1, {"utterances": [], "negative_samples": []})
    result = system.sync.sync()
    assert result["positive_points"] == 0 and result["description_points"] == 1
    assert system.qdrant_client.index_summary()["points_count"] == 1
    assert PredictionService(system).route("查询")["match_source"] == "llm_fallback"


def test_edit_during_model_call_rejects_stale_selection(system, model, monkeypatch):
    classify = FallbackService._classify

    def edit(query, candidates):
        system.agent_store.update(1, {"text": "新职责"})
        return classify(query, candidates)

    monkeypatch.setattr(FallbackService, "_classify", staticmethod(edit))
    assert PredictionService(system).route("查询")["fallback_status"] == "no_candidates"


def test_sync_write_failure_does_not_acknowledge_changed_hash(system, monkeypatch):
    previous = agent_hash(system.agent_store.get(1))
    system.agent_store.update(1, {"text": "更改职责"})

    def fail(*args, **kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(system.qdrant_client, "upsert_routes", fail)
    with pytest.raises(RuntimeError, match="write failed"):
        system.sync.sync()
    with system.sync._open_state() as connection:
        assert system.sync._load_hashes(connection, "test")[1] == previous


@pytest.mark.parametrize("failure", ["timeout", "401"])
def test_model_failure_is_bounded_without_retry(system, model, failure):
    if failure == "timeout":
        model.delay = 5
    else:
        model.status = 401
    result = PredictionService(system).route("查询")
    assert result["fallback_status"] == "unavailable"
    assert len(model.calls) == 1


@pytest.mark.parametrize("values", [
    {"LLM_FALLBACK_ENABLED": "false"}, {"LLM_FALLBACK_TOP_K": 0},
    {"LLM_FALLBACK_TOP_K": 21}, {"LLM_FALLBACK_TOP_K": True},
    {"LLM_FALLBACK_TIMEOUT_SECONDS": 0}, {"LLM_FALLBACK_TIMEOUT_SECONDS": float("nan")},
])
def test_settings_reject_invalid_values_before_mutation(system, tmp_path, monkeypatch, values):
    monkeypatch.setattr(Config, "SETTINGS_FILE", tmp_path / "settings.json")
    before = Config.to_dict()
    with pytest.raises(ValueError):
        Config.save(values)
    assert not Config.SETTINGS_FILE.exists() and Config.to_dict() == before


def test_route_api_preserves_bupt_envelope_and_auth(system, model, monkeypatch):
    from intent_hub.app import app

    monkeypatch.setattr(Config, "AUTH_CODE", "test-auth-code")
    monkeypatch.setattr("intent_hub.app.get_component_manager", lambda: system)
    client = app.test_client()
    assert client.post("/route", json={"query": "查询"}).status_code == 401
    response = client.post("/route", json={"query": "查询"}, headers={"Authorization": "Bearer test-auth-code"})
    assert response.status_code == 200
    result = response.get_json()
    assert result["success"] is True and result["error"] is None
    assert result["data"]["match_source"] == "llm_fallback"
    assert client.post("/predict", json={"text": "查询"}).status_code == 404


def test_settings_api_saves_controls_without_exposing_secrets(system, tmp_path, monkeypatch):
    from intent_hub.app import app

    monkeypatch.setattr(Config, "AUTH_CODE", "test-auth-code")
    monkeypatch.setattr(Config, "SETTINGS_FILE", tmp_path / "settings.json")
    monkeypatch.setattr("intent_hub.app.get_component_manager", lambda: SimpleNamespace(reinit_components=lambda: None))
    client = app.test_client()
    headers = {"Authorization": "Bearer test-auth-code"}
    response = client.post("/settings", json={"LLM_FALLBACK_TOP_K": 3}, headers=headers)
    assert response.status_code == 200
    assert response.get_json()["settings"]["LLM_FALLBACK_TOP_K"] == 3
    assert "LLM_API_KEY" not in response.get_json()["settings"]
    before = Config.SETTINGS_FILE.read_bytes()
    assert client.post("/settings", json={"LLM_FALLBACK_TOP_K": 0}, headers=headers).status_code == 400
    assert Config.SETTINGS_FILE.read_bytes() == before and Config.LLM_FALLBACK_TOP_K == 3


def test_gemini_uses_constrained_instructions_and_private_header(system, monkeypatch):
    original = httpx.AsyncClient
    monkeypatch.setattr(Config, "LLM_PROVIDER", "gemini")

    def handler(request):
        body = json.loads(request.content)
        assert request.headers["x-goog-api-key"] == "local-test-key"
        assert "key=" not in str(request.url)
        assert body["generationConfig"]["temperature"] == 0
        assert "systemInstruction" in body
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [
            {"text": '{"status":"no_match","route_id":null}'}]}}]})

    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert PredictionService(system).route("查询")["fallback_status"] == "no_match"


def test_consecutive_real_http_calls_use_request_scoped_clients(system, monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def do_POST(self):
            self.rfile.read(int(self.headers["Content-Length"]))
            data = json.dumps({"choices": [{"message": {"content": '{"status":"matched","route_id":1}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setattr(Config, "LLM_BASE_URL", f"http://127.0.0.1:{server.server_port}")
    # This checks repeated event loops, not the 1-second deadline tested above.
    monkeypatch.setattr(Config, "LLM_FALLBACK_TIMEOUT_SECONDS", 5)
    try:
        for _ in range(3):
            assert PredictionService(system).route("查询")["fallback_status"] == "matched"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
