import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager
from intent_hub.services.import_service import ImportService
from intent_hub.services.route_service import RouteService


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class DummyComponentManager:
    def __init__(self, routes_path: Path):
        self.route_manager = RouteManager(config_path=str(routes_path))

    def ensure_ready(self):
        return None


def test_create_route_marks_source_as_web_manual(test_dir):
    manager = DummyComponentManager(test_dir / "routes.json")
    service = RouteService(manager)

    route = service.create_route(
        RouteConfig(
            id=0,
            name="天气服务",
            route_key="weather.query",
            description="返回天气信息",
            utterances=["查天气"],
            negative_samples=[],
            score_threshold=0.85,
            negative_threshold=0.95,
        )
    )

    assert route.source is not None
    assert route.source.type == "web_manual"
    saved = json.loads((test_dir / "routes.json").read_text(encoding="utf-8"))
    assert saved[0]["source"]["type"] == "web_manual"


def test_import_service_marks_imported_routes_as_json_import(test_dir):
    manager = DummyComponentManager(test_dir / "routes.json")
    service = ImportService(manager)

    result = service.import_routes(
        routes=[
            RouteConfig(
                id=0,
                name="知识库构建",
                route_key="obsidian.wiki.build",
                description="构建 wiki",
                utterances=["整理 wiki"],
                negative_samples=[],
                score_threshold=0.8,
                negative_threshold=0.95,
            )
        ],
        mode="merge",
        import_origin="api_import",
    )

    assert result["created"] == 1
    saved = json.loads((test_dir / "routes.json").read_text(encoding="utf-8"))
    assert saved[0]["source"]["type"] == "json_import"
    assert saved[0]["source"]["import_origin"] == "api_import"


def test_import_service_rejects_duplicate_route_keys_in_payload(test_dir):
    manager = DummyComponentManager(test_dir / "routes.json")
    service = ImportService(manager)

    with pytest.raises(ValueError, match="Duplicate route_key in import payload"):
        service.import_routes(
            routes=[
                RouteConfig(
                    id=0,
                    name="A",
                    route_key="same.key",
                    description="",
                    utterances=["a"],
                    negative_samples=[],
                    score_threshold=0.8,
                    negative_threshold=0.95,
                ),
                RouteConfig(
                    id=0,
                    name="B",
                    route_key="same.key",
                    description="",
                    utterances=["b"],
                    negative_samples=[],
                    score_threshold=0.8,
                    negative_threshold=0.95,
                ),
            ],
            mode="merge",
        )


def test_import_service_rejects_route_key_conflict_with_existing_routes(test_dir):
    manager = DummyComponentManager(test_dir / "routes.json")
    service = ImportService(manager)
    service.import_routes(
        routes=[
            RouteConfig(
                id=0,
                name="现有路由",
                route_key="existing.key",
                description="",
                utterances=["a"],
                negative_samples=[],
                score_threshold=0.8,
                negative_threshold=0.95,
            )
        ],
        mode="merge",
    )

    with pytest.raises(ValueError, match="route_key 冲突"):
        service.import_routes(
            routes=[
                RouteConfig(
                    id=0,
                    name="冲突路由",
                    route_key="existing.key",
                    description="",
                    utterances=["b"],
                    negative_samples=[],
                    score_threshold=0.8,
                    negative_threshold=0.95,
                )
            ],
            mode="merge",
        )


def test_import_service_rejects_managed_route_key_override(test_dir):
    manager = DummyComponentManager(test_dir / "routes.json")
    service = ImportService(manager)
    created = service.import_routes(
        routes=[
            RouteConfig(
                id=0,
                name="受托管路由",
                route_key="managed.key",
                description="",
                utterances=["a"],
                negative_samples=[],
                score_threshold=0.8,
                negative_threshold=0.95,
                source=RouteConfig.RouteSource(
                    type="json_import",
                    managed_fields=["route_key"],
                ),
            )
        ],
        mode="merge",
        import_origin="skill_scan",
    )
    assert created["created"] == 1
    saved = json.loads((test_dir / "routes.json").read_text(encoding="utf-8"))
    route_id = saved[0]["id"]

    with pytest.raises(ValueError, match="托管字段冲突"):
        service.import_routes(
            routes=[
                RouteConfig(
                    id=route_id,
                    name="受托管路由",
                    route_key="managed.key.changed",
                    description="",
                    utterances=["a"],
                    negative_samples=[],
                    score_threshold=0.8,
                    negative_threshold=0.95,
                    source=RouteConfig.RouteSource(
                        type="json_import",
                        managed_fields=["route_key"],
                    ),
                )
            ],
            mode="merge",
            import_origin="skill_scan",
        )
