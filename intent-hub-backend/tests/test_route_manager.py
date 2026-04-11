"""路由管理器测试"""

import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager


@pytest.fixture
def test_dir():
    """在仓库内创建临时测试目录，避免系统临时目录权限问题"""
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_load_routes_migrates_missing_route_key(test_dir):
    """缺少 route_key 的旧数据会在加载时自动补齐并持久化"""
    config_path = test_dir / "routes.json"
    config_path.write_text(
        json.dumps(
            [
                {
                    "id": 1,
                    "name": "天气服务",
                    "description": "返回天气信息",
                    "utterances": ["查天气"],
                    "negative_samples": [],
                    "score_threshold": 0.85,
                    "negative_threshold": 0.95,
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manager = RouteManager(config_path=str(config_path))
    route = manager.get_route(1)

    assert route is not None
    assert route.route_key == "天气服务"

    saved_routes = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved_routes[0]["route_key"] == "天气服务"


def test_add_route_rejects_duplicate_route_key(test_dir):
    """route_key 必须全局唯一"""
    manager = RouteManager(config_path=str(test_dir / "routes.json"))

    manager.add_route(
        RouteConfig(
            id=1,
            name="天气服务",
            route_key="weather.query",
            description="返回天气信息",
            utterances=["查天气"],
            negative_samples=[],
            score_threshold=0.85,
            negative_threshold=0.95,
        )
    )

    with pytest.raises(ValueError, match="route_key 'weather.query' already exists"):
        manager.add_route(
            RouteConfig(
                id=2,
                name="天气服务2",
                route_key="weather.query",
                description="返回天气信息",
                utterances=["看天气"],
                negative_samples=[],
                score_threshold=0.85,
                negative_threshold=0.95,
            )
        )
