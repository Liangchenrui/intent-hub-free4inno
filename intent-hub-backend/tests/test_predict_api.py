from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import PredictResponse


class DummyComponentManager:
    def ensure_ready(self):
        pass


class DummyPredictionService:
    def __init__(self, component_manager):
        self.component_manager = component_manager

    def predict(self, request):
        return [PredictResponse(id=7, name="route-for-single", route_key="single.route", score=0.91)]


def test_predict_uses_independent_route_key(monkeypatch):
    monkeypatch.setattr(Config, "PREDICT_AUTH_KEY", "route-secret")
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    monkeypatch.setattr("intent_hub.api.prediction.get_component_manager", lambda: DummyComponentManager())
    monkeypatch.setattr("intent_hub.api.prediction.PredictionService", DummyPredictionService)

    client = app.test_client()
    unauthorized = client.post("/predict", json={"text": "organize wiki"})
    response = client.post(
        "/predict",
        headers={"Authorization": "Bearer route-secret"},
        json={"text": "organize wiki"},
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.get_json()[0]["route_key"] == "single.route"
