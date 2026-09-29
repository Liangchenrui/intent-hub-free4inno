from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import PredictResponse


from types import SimpleNamespace


class DummyComponentManager:
    route_manager = SimpleNamespace(get_route=lambda _: SimpleNamespace(details={}))
    def ensure_ready(self):
        pass


class DummyPredictionService:
    def __init__(self, component_manager):
        self.component_manager = component_manager

    def predict(self, request):
        return [PredictResponse(id=7, name="route-for-single", route_key="single.route", score=0.91)]


def test_predict_uses_independent_route_key(monkeypatch):
    monkeypatch.setattr(Config, "ROUTE_API_KEY", "route-secret")
    monkeypatch.setattr(Config, "AUTH_ENABLED", False)
    monkeypatch.setattr("intent_hub.api.prediction.get_component_manager", lambda: DummyComponentManager())
    monkeypatch.setattr("intent_hub.api.prediction.PredictionService", DummyPredictionService)

    client = app.test_client()
    unauthorized = client.post("/route", json={"query": "organize wiki"})
    response = client.post(
        "/route",
        headers={"Authorization": "Bearer route-secret"},
        json={"query": "organize wiki"},
    )

    assert unauthorized.status_code == 401
    assert response.status_code == 200
    assert response.get_json()["data"]["agents"][0]["route_key"] == "single.route"


def test_only_one_routing_endpoint():
    client = app.test_client()
    for path in ['/predict', '/compat/master/predict', '/compat/bupt/route', '/compat/master/route']:
        assert client.post(path, json={'query': 'test'}).status_code == 404
    assert sum(rule.rule == '/route' for rule in app.url_map.iter_rules()) == 1


def test_invalid_json_and_removed_fields(monkeypatch):
    monkeypatch.setattr(Config, 'ROUTE_API_KEY', 'test-key')
    client = app.test_client()
    headers = {'X-API-Key': 'test-key'}
    for payload in [[], None, {'query': ' '}, {'text': 'old'}, {'query': 'ok', 'typo': True}, {'query': 'ok', 'learn_from_fallback': 'false'}]:
        response = client.post('/route', json=payload, headers=headers)
        assert response.status_code == 400
        assert response.json['error']['code'] == 'INVALID_REQUEST'
    response = client.post('/route', data='{bad', content_type='application/json', headers=headers)
    assert response.status_code == 400


def test_admin_session_can_use_test_page(monkeypatch):
    monkeypatch.setattr(Config, 'AUTH_ENABLED', True)
    monkeypatch.setattr('intent_hub.api.prediction.get_auth_manager', lambda: SimpleNamespace(is_valid=lambda key: key == 'session'))
    monkeypatch.setattr('intent_hub.api.prediction.get_component_manager', DummyComponentManager)
    class CaptureService(DummyPredictionService):
        def predict(self, request):
            assert request.learn_from_fallback is False
            return super().predict(request)
    monkeypatch.setattr('intent_hub.api.prediction.PredictionService', CaptureService)
    response = app.test_client().post('/route', json={'query': 'test', 'learn_from_fallback': False}, headers={'Authorization': 'Bearer session'})
    assert response.status_code == 200
