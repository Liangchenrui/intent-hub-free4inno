"""Scope isolation with real in-memory Qdrant and offline embeddings."""
import pytest
from qdrant_client.models import Distance, VectorParams

from intent_hub.models import PredictRequest, RouteConfig
from intent_hub.models import RouteRequest
from intent_hub.services.prediction_service import PredictionService
from intent_hub.services.sync_service import SyncService
from tests.test_llm_fallback import system, set_model


@pytest.mark.parametrize("model,body", [(PredictRequest, {"text": "test"}), (RouteRequest, {"query": "test"})])
@pytest.mark.parametrize("field", ["collection", "upstream_id"])
def test_scope_validation(model, body, field):
    for value in ["", "   ", 123, []]:
        with pytest.raises(ValueError):
            model(**body, **{field: value})
    assert getattr(model(**body, **{field: " a "}), field) == "a"
    assert getattr(model(**body), field) is None


def test_upstream_limits_semantic_and_fallback(system, monkeypatch):
    first = system.route_manager.get_route(1).model_copy(deep=True)
    first.source = RouteConfig.RouteSource(type="upstream_agent", instance="one")
    first.utterances = ["名称：positive"]
    system.route_manager.add_route(first)
    second = first.model_copy(deep=True)
    second.id = 2
    second.route_key = "two.orders"
    second.source.instance = "two"
    system.route_manager.add_route(second)
    SyncService(system).sync_route(1)
    SyncService(system).sync_route(2)
    service = PredictionService(system)
    assert {r.id for r in service.predict(PredictRequest(text="test"))} == {1, 2}
    assert [r.id for r in service.predict(PredictRequest(text="test", upstream_id="two"))] == [2]
    assert not hasattr(system.qdrant_client, "search_route_ids")
    missing = service.predict(PredictRequest(text="test", upstream_id="missing"))[0]
    assert missing.match_source == "default"
    assert missing.fallback_status == "no_candidates"
    # Remove semantic matches; the model must only see the requested upstream.
    first.utterances = ["positive"]
    second.utterances = ["positive"]
    system.route_manager.add_route(first)
    system.route_manager.add_route(second)
    SyncService(system).sync_route(1)
    SyncService(system).sync_route(2)
    calls = []
    set_model(monkeypatch, '{"status":"matched","route_id":1}', calls)
    result = service.predict(PredictRequest(text="test", upstream_id="two", learn_from_fallback=False))[0]
    assert result.match_source == "default"
    assert len(calls) == 1
    import json
    assert [c["route_id"] for c in json.loads(calls[0][1].content)["candidates"]] == [2]


def test_collection_isolation_and_missing_collection(system, monkeypatch):
    service = PredictionService(system)
    system.qdrant_client.client.create_collection("empty", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    result = service.predict(PredictRequest(text="test", collection="empty"))[0]
    assert result.match_source == "default"
    assert result.fallback_status == "no_candidates"
    assert system.qdrant_client.collection_name == "test"
    with pytest.raises(ValueError, match="不存在"):
        service.predict(PredictRequest(text="test", collection="missing"))
    assert not system.qdrant_client.client.collection_exists("missing")
    set_model(monkeypatch, '{"status":"matched","route_id":1}')
    assert service.predict(PredictRequest(text="test", learn_from_fallback=False))[0].id == 1


@pytest.mark.parametrize("url,key", [("/route", "query")])
def test_http_scope_contract(system, monkeypatch, url, key):
    from intent_hub.app import app
    from intent_hub.config import Config
    monkeypatch.setattr(Config, "ROUTE_API_KEY", "scope-test-key")
    monkeypatch.setattr("intent_hub.api.prediction.get_component_manager", lambda: system)
    client = app.test_client()
    headers = {"Authorization": "Bearer scope-test-key"}
    response = client.post(url, headers=headers, json={key: "test", "upstream_id": "missing"})
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert body["data"]["matched"] is False
    for scope in [{"collection": "missing"}, {"collection": "  "}, {"upstream_id": 42}]:
        assert client.post(url, headers=headers, json={key: "test", **scope}).status_code == 400


def test_combined_scope_uses_selected_collection_without_learning(system, monkeypatch):
    from copy import copy
    route = system.route_manager.get_route(1).model_copy(deep=True)
    route.source = RouteConfig.RouteSource(type="upstream_agent", instance="one")
    system.route_manager.add_route(route)
    other = copy(system)
    other.qdrant_client = copy(system.qdrant_client)
    other.qdrant_client.collection_name = "other"
    other.qdrant_client.client.create_collection("other", vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    SyncService(other).sync_route(1)
    set_model(monkeypatch, '{"status":"matched","route_id":1}')
    result = PredictionService(system).predict(PredictRequest(
        text="new sample", collection="other", upstream_id="one"))[0]
    assert result.match_source == "llm_fallback"
    assert result.id == 1
    system.route_manager.reload()
    assert "new sample" not in system.route_manager.get_route(1).utterances
    assert system.qdrant_client.collection_name == "test"
