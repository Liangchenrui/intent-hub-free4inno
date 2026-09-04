import pytest

from intent_hub.config import Config
from intent_hub.services.collection_service import CollectionService


def test_create_collection_validates_name_and_uses_embedding_dimensions(monkeypatch):
    monkeypatch.setattr(
        CollectionService,
        "list_collections",
        lambda self: {"collections": [{"name": "existing"}]},
    )
    calls = []

    def factory(**kwargs):
        calls.append(kwargs)

    components = type(
        "Components",
        (),
        {"encoder": type("Encoder", (), {"dimensions": 1024})()},
    )()
    result = CollectionService(components, client_factory=factory).create_collection("new_routes")

    assert result == {"name": "new_routes", "kind": "collection", "target": None}
    assert calls[0]["dimensions"] == 1024
    assert calls[0]["collection_name"] == "new_routes"

    with pytest.raises(ValueError, match="仅支持"):
        CollectionService(components, client_factory=factory).create_collection("bad/name")
    with pytest.raises(ValueError, match="已存在"):
        CollectionService(components, client_factory=factory).create_collection("existing")
