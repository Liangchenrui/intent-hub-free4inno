from intent_hub.models import PredictRequest, RouteConfig
from intent_hub.services.prediction_service import PredictionService


class FakeEncoder:
    def encode_single(self, text):
        return [1.0, 0.0]


class FakeQdrantClient:
    ROUTE_ID_KEY = "route_id"
    ROUTE_NAME_KEY = "route_name"
    UTTERANCE_KEY = "utterance"
    SCORE_THRESHOLD_KEY = "score_threshold"
    NEGATIVE_THRESHOLD_KEY = "negative_threshold"

    def search_negative_samples(self, query_vector, top_k=20):
        return []

    def search(self, query_vector, top_k=20):
        return [
            {
                "score": 0.91,
                "payload": {
                    self.ROUTE_ID_KEY: 1,
                    self.ROUTE_NAME_KEY: "Old Route",
                    self.SCORE_THRESHOLD_KEY: 0.75,
                },
            }
        ]


class ReloadingRouteManager:
    def __init__(self):
        self.reload_called = False
        self.route = RouteConfig(
            id=1,
            name="Old Route",
            route_key="old.route",
            description="",
            utterances=["old"],
            score_threshold=0.75,
        )

    def reload(self):
        self.reload_called = True
        self.route = RouteConfig(
            id=1,
            name="New Route",
            route_key="new.route",
            description="",
            utterances=["new"],
            score_threshold=0.75,
        )

    def get_route(self, route_id):
        return self.route if route_id == self.route.id else None

    def get_score_threshold(self, route_id):
        route = self.get_route(route_id)
        return route.score_threshold if route else None


class FakeComponentManager:
    def __init__(self):
        self.encoder = FakeEncoder()
        self.qdrant_client = FakeQdrantClient()
        self.route_manager = ReloadingRouteManager()

    def ensure_ready(self):
        return None


def test_predict_reloads_route_config_before_resolving_match_metadata():
    component_manager = FakeComponentManager()
    service = PredictionService(component_manager)

    results = service.predict(PredictRequest(text="test query"))

    assert component_manager.route_manager.reload_called is True
    assert results[0].name == "New Route"
    assert results[0].route_key == "new.route"
