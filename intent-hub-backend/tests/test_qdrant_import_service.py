import json

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager
from intent_hub.services.qdrant_import_service import QdrantImportService


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "result": {
                "points": [
                    {
                        "payload": {
                            "route_id": 1,
                            "route_name": "OrderTracking",
                            "utterance": "Where is my order?",
                            "score_threshold": 0.8,
                        }
                    },
                    {
                        "payload": {
                            "route_id": 1,
                            "route_name": "OrderTracking",
                            "utterance": "Cancel my order",
                            "is_negative": True,
                            "negative_threshold": 0.9,
                        }
                    },
                ],
                "next_page_offset": None,
            }
        }


def test_import_collection_recovers_routes_and_preserves_matching_metadata(tmp_path, monkeypatch):
    routes_path = tmp_path / "routes.json"
    routes_path.write_text(
        json.dumps(
            [
                RouteConfig(
                    id=9,
                    name="OrderTracking",
                    route_key="orders.track",
                    description="Track an existing order",
                    utterances=["old"],
                ).model_dump()
            ]
        ),
        encoding="utf-8",
    )
    manager = RouteManager(str(routes_path))
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example.com")
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")
    monkeypatch.setattr(
        "intent_hub.services.qdrant_import_service.requests.post",
        lambda *args, **kwargs: FakeResponse(),
    )

    routes = QdrantImportService(manager).import_collection("support routes")

    assert len(routes) == 1
    assert routes[0].id == 1
    assert routes[0].route_key == "orders.track"
    assert routes[0].description == "Track an existing order"
    assert routes[0].utterances == ["Where is my order?"]
    assert routes[0].negative_samples == ["Cancel my order"]
    assert routes[0].score_threshold == 0.8
    assert routes[0].negative_threshold == 0.9
    assert manager.get_all_routes()[0].source.import_origin == "qdrant:support routes"


def test_complete_metadata_point_takes_priority_over_vector_payloads(tmp_path):
    routes_path = tmp_path / "routes.json"
    routes_path.write_text("[]", encoding="utf-8")
    manager = RouteManager(str(routes_path))
    expected = RouteConfig(
        id=3,
        name="Refunds",
        route_key="orders.refund",
        description="Handle complete refund workflows",
        utterances=["Refund this order"],
        negative_samples=["Track this order"],
        score_threshold=0.82,
        negative_threshold=0.93,
        lifecycle_status="disabled",
    )
    points = [
        {
            "payload": {
                "route_id": 3,
                "route_name": "Refunds",
                "is_route_metadata": True,
                "route_config": expected.model_dump(),
            }
        },
        {
            "payload": {
                "route_id": 3,
                "route_name": "Refunds",
                "utterance": "legacy utterance",
            }
        },
    ]

    recovered = QdrantImportService(manager)._build_routes(points, "orders")

    assert recovered == [expected]
