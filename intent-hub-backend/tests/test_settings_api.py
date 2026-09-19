from intent_hub.api import settings
from intent_hub.app import app
from intent_hub.config import Config
from types import SimpleNamespace
from unittest.mock import Mock
import pytest


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


def test_list_qdrant_collections_uses_configured_url(monkeypatch):
    calls = []
    monkeypatch.setattr(Config, "QDRANT_URL", "http://qdrant.example.com/base/")
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "secret")

    def fake_get(url, **kwargs):
        calls.append((url, kwargs))
        if url.endswith("/aliases"):
            return FakeResponse({"result": {"aliases": [{"alias_name": "active", "collection_name": "a_collection"}]}})
        return FakeResponse({"result": {"collections": [{"name": "z_collection"}, {"name": "a_collection"}]}})

    monkeypatch.setattr("intent_hub.services.collection_service.requests.get", fake_get)

    with app.test_request_context():
        response, status = settings.list_qdrant_collections()

    assert status == 200
    payload = response.get_json()
    assert payload["items"] == ["a_collection", "active", "z_collection"]
    assert payload["collections"][1] == {"name": "active", "kind": "alias", "target": "a_collection"}
    assert [call[0] for call in calls] == [
        "http://qdrant.example.com/base/collections",
        "http://qdrant.example.com/base/aliases",
    ]
    assert all(call[1] == {"headers": {"api-key": "secret"}, "timeout": 10} for call in calls)


@pytest.mark.parametrize('change,reset,queued', [
    ({}, False, False),
    ({'LLM_FALLBACK_TOP_K': 3}, False, False),
    ({'BATCH_SIZE': 17}, True, False),
    ({'SERVICE_HTTP_TRUST_ENV': False}, True, False),
    ({'QDRANT_COLLECTION': 'new-target'}, True, True),
    ({'EMBEDDING_MODEL_NAME': 'new-model'}, True, True),
    ({'EMBEDDING_SERVICE_URL': 'http://new-encoder/embed'}, True, True),
])
def test_settings_only_reacts_to_actual_changes(tmp_path, monkeypatch, change, reset, queued):
    # Real config validation/persistence, isolated from the user's settings.
    for key in Config.to_dict():
        monkeypatch.setattr(Config, key, getattr(Config, key))
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(tmp_path / 'settings.json'))
    monkeypatch.setattr(Config, 'LLM_FALLBACK_TOP_K', 5)
    monkeypatch.setattr(Config, 'SERVICE_HTTP_TRUST_ENV', True)
    manager = SimpleNamespace(reset_components=Mock())
    queue = SimpleNamespace(enqueue_incremental_reindex=Mock())
    monkeypatch.setattr('intent_hub.core.components.get_component_manager', lambda: manager)
    monkeypatch.setattr('intent_hub.services.sync_task_service.get_sync_task_service', lambda _: queue)
    payload = {key: getattr(Config, key) for key in (
        'QDRANT_COLLECTION', 'EMBEDDING_MODEL_NAME', 'EMBEDDING_SERVICE_URL', 'BATCH_SIZE')}
    payload.update(change)
    with app.test_request_context(json=payload):
        response, status = settings.update_settings()
    assert status == 200, response.get_json()
    assert manager.reset_components.call_count == int(reset)
    assert queue.enqueue_incremental_reindex.call_count == int(queued)
    # A second identical submission must not reset or enqueue again.
    with app.test_request_context(json=payload):
        assert settings.update_settings()[1] == 200
    assert manager.reset_components.call_count == int(reset)
    assert queue.enqueue_incremental_reindex.call_count == int(queued)


def test_proxy_setting_rejects_strings_before_persistence(tmp_path, monkeypatch):
    path = tmp_path / 'settings.json'
    path.write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(path))
    with pytest.raises(ValueError, match='boolean'):
        Config.save({'SERVICE_HTTP_TRUST_ENV': 'false'})
    assert path.read_text(encoding='utf-8') == '{}'
