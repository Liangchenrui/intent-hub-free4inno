import pytest

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.services.sync_service import SyncService


def route(route_id=1):
    return RouteConfig(
        id=route_id,
        name=f"Route {route_id}",
        route_key=f"route.{route_id}",
        utterances=["hello"],
        negative_samples=["goodbye"],
    )


def test_incremental_sync_blocks_abnormal_mass_deletion(monkeypatch):
    monkeypatch.setattr(Config, "MAX_DELETE_RATIO", 0.2)

    class RouteManager:
        def reload(self):
            pass

        def get_all_routes(self):
            return [route(1)]

    class Qdrant:
        def get_existing_route_hashes(self):
            return {item: "hash" for item in range(1, 11)}

        def delete_route(self, _route_id):
            raise AssertionError("deletion must be rejected before changing Qdrant")

    manager = type(
        "Manager",
        (),
        {
            "ensure_ready": lambda self: None,
            "route_manager": RouteManager(),
            "qdrant_client": Qdrant(),
            "encoder": object(),
        },
    )()

    with pytest.raises(ValueError, match="超过安全阈值"):
        SyncService(manager).reindex()


def test_index_validation_checks_points_routes_and_hashes():
    item = route(7)

    class RouteManager:
        @staticmethod
        def compute_route_hash(_route):
            return "expected-hash"

    class Qdrant:
        @staticmethod
        def index_summary():
            return {
                "points_count": 3,
                "route_ids": [7],
                "route_hashes": {7: "expected-hash"},
            }

    SyncService._validate_index([item], Qdrant(), RouteManager())

    class InvalidQdrant(Qdrant):
        @staticmethod
        def index_summary():
            return {"points_count": 2, "route_ids": [7], "route_hashes": {}}

    with pytest.raises(RuntimeError, match="索引校验失败"):
        SyncService._validate_index([item], InvalidQdrant(), RouteManager())
