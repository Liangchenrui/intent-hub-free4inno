import requests

from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.services.health_service import check_external_services


class Response:
    def __init__(self, status_code):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400


def test_external_health_uses_ports_paths_and_qdrant_key(monkeypatch):
    monkeypatch.setattr(Config, "EMBEDDING_SERVICE_URL", "https://embed.example:9443/v1/embed")
    monkeypatch.setattr(Config, "EMBEDDING_HEALTH_URL", None)
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example:6333/gateway")
    monkeypatch.setattr(Config, "QDRANT_HEALTH_URL", None)
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return Response(200 if "embed" in url else 503)

    monkeypatch.setattr("intent_hub.services.health_service.requests.get", get)
    result = check_external_services()

    assert {call[0] for call in calls} == {
        "https://embed.example:9443/health",
        "http://qdrant.example:6333/healthz",
    }
    qdrant_call = next(call for call in calls if "qdrant" in call[0])
    assert qdrant_call[1]["headers"] == {"api-key": "secret"}
    assert result["status"] == "degraded"


def test_external_health_hides_connection_exception(monkeypatch):
    monkeypatch.setattr(Config, "EMBEDDING_HEALTH_URL", "https://embed.example/status")
    monkeypatch.setattr(Config, "QDRANT_HEALTH_URL", "https://qdrant.example/status")

    def fail(*_args, **_kwargs):
        raise requests.ConnectionError("private upstream details")

    monkeypatch.setattr("intent_hub.services.health_service.requests.get", fail)
    result = check_external_services()

    assert result["services"]["embedding"]["message"] == "connection failed"
    assert "private" not in str(result)


def test_health_routes_separate_liveness_and_authenticated_services(monkeypatch):
    monkeypatch.setattr(Config, "AUTH_ENABLED", True)
    client = app.test_client()

    assert client.get("/health").status_code == 200
    assert client.get("/health/services").status_code == 401
