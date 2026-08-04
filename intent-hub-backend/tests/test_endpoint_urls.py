import pytest

from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.models import RouteConfig
from intent_hub.qdrant_wrapper import IntentHubQdrantClient


class FakeQdrantSdk:
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def collection_exists(self, _name):
        return True


class FakeEmbeddingResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"output": {"embeddings": [{"text_index": 0, "embedding": [0.1, 0.2]}]}}


def test_qdrant_complete_url_is_passed_without_default_port(monkeypatch):
    created = {}

    def factory(**kwargs):
        created.update(kwargs)
        return FakeQdrantSdk(**kwargs)

    monkeypatch.setattr("intent_hub.qdrant_wrapper.QdrantClient", factory)
    url = "https://cluster.cloud.qdrant.io:6333/custom"

    IntentHubQdrantClient(url=url, collection_name="routes", dimensions=2)

    assert created["url"] == url
    assert "host" not in created


def test_embedding_complete_url_only_gets_endpoint_path(monkeypatch):
    calls = []

    def post(url, **kwargs):
        calls.append(url)
        return FakeEmbeddingResponse()

    monkeypatch.setattr("intent_hub.encoder.requests.post", post)
    encoder = QwenEmbeddingEncoder("https://embedding.example.com:9443/api")

    assert encoder.endpoint_url == "https://embedding.example.com:9443/api/get_embeddings"
    assert calls == [encoder.endpoint_url]


@pytest.mark.parametrize("client,url", [(IntentHubQdrantClient, "qdrant.local"), (QwenEmbeddingEncoder, "embedding.local")])
def test_service_addresses_require_complete_urls(client, url):
    with pytest.raises(ValueError, match="complete http"):
        if client is IntentHubQdrantClient:
            client(url=url, collection_name="routes", dimensions=2)
        else:
            client(url)


class CaptureQdrantClient:
    def __init__(self):
        self.points = None
        self.query_filter = None

    def upsert(self, collection_name, points):
        self.points = points

    def query_points(self, **kwargs):
        self.query_filter = kwargs["query_filter"]
        return type("Result", (), {"points": []})()


def test_route_metadata_is_complete_and_excluded_from_search():
    wrapper = object.__new__(IntentHubQdrantClient)
    wrapper.collection_name = "routes"
    wrapper.dimensions = 3
    wrapper.client = CaptureQdrantClient()
    route = RouteConfig(
        id=4,
        name="Orders",
        route_key="orders.track",
        description="Track orders",
        utterances=["Where is it?"],
        negative_samples=["Cancel it"],
        score_threshold=0.81,
        negative_threshold=0.91,
    )

    wrapper.upsert_route_metadata(route)
    point = wrapper.client.points[0]
    assert point.vector == [0.0, 0.0, 0.0]
    assert point.payload[wrapper.IS_ROUTE_METADATA_KEY] is True
    assert point.payload[wrapper.ROUTE_CONFIG_KEY] == route.model_dump()

    wrapper.search([0.1, 0.2, 0.3])
    excluded_keys = {condition.key for condition in wrapper.client.query_filter.must_not}
    assert wrapper.IS_ROUTE_METADATA_KEY in excluded_keys
    assert wrapper.IS_NEGATIVE_KEY in excluded_keys
