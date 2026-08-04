import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class DummyEncoder:
    def __init__(self, service_url: str, batch_size: int):
        self.service_url = service_url
        self.batch_size = batch_size
        self.dimensions = 3


class DummyQdrantClient:
    def __init__(self, url: str, collection_name: str, dimensions: int, api_key=None):
        self.url = url
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.api_key = api_key


def test_component_manager_uses_single_workspace(test_dir, monkeypatch):
    monkeypatch.setattr(Config, "DATA_DIR", test_dir)
    monkeypatch.setattr(Config, "ROUTES_CONFIG_PATH", str(test_dir / "routes.json"))
    (test_dir / "routes.json").write_text("[]", encoding="utf-8")

    manager = ComponentManager(
        encoder_factory=DummyEncoder,
        qdrant_client_factory=DummyQdrantClient,
    )

    manager.ensure_ready()

    assert manager.route_manager.config_path == str(test_dir / "routes.json")
    assert manager.qdrant_client.collection_name == Config.QDRANT_COLLECTION
