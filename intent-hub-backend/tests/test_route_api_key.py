"""Settings persistence and authentication with real HTTP decorators, no providers."""
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from intent_hub.app import app
from intent_hub.config import Config


@pytest.fixture
def client(tmp_path, monkeypatch):
    for key in set(Config.to_dict()) | Config.SECRET_KEYS:
        monkeypatch.setattr(Config, key, getattr(Config, key))
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(tmp_path / 'settings.json'))
    monkeypatch.setattr(Config, 'ROUTE_API_KEY', '')
    monkeypatch.setattr(Config, 'AUTH_ENABLED', True)
    monkeypatch.setattr(Config, 'PREDICT_AUTH_KEY', 'legacy-master')
    monkeypatch.setattr(Config, 'AUTH_CODE', 'legacy-bupt')
    monkeypatch.setenv('PREDICT_AUTH_KEY', 'legacy-master')
    monkeypatch.setenv('AUTH_CODE', 'legacy-bupt')
    monkeypatch.setattr('intent_hub.core.components.get_component_manager',
                        lambda: SimpleNamespace(reset_components=Mock()))
    return app.test_client()


def admin_headers(client):
    response = client.post('/compat/master/auth/login', json={
        'username': Config.DEFAULT_USERNAME, 'password': Config.DEFAULT_PASSWORD})
    assert response.status_code == 200
    return {'Authorization': 'Bearer ' + response.get_json()['api_key']}


def assert_key(client, key, accepted):
    for url in ['/predict', '/compat/master/predict', '/route', '/compat/bupt/route']:
        response = client.post(url, headers={'Authorization': 'Bearer ' + key}, json={'text': '', 'query': ''})
        # Valid auth reaches input validation, without invoking a real model.
        assert response.status_code == (400 if accepted else 401), (url, response.get_json())


def test_save_rotate_reload_and_clear(client):
    headers = admin_headers(client)
    for key in ['shared-first', 'shared-rotated']:
        response = client.post('/compat/master/settings', headers=headers, json={'ROUTE_API_KEY': key})
        assert response.status_code == 200, response.get_json()
        assert response.get_json()['settings']['ROUTE_API_KEY'] == key
        assert json.loads(Config.get_settings_path().read_text(encoding='utf-8'))['ROUTE_API_KEY'] == key
        assert_key(client, key, True)
        assert_key(client, 'wrong-key', False)
        assert_key(client, 'legacy-master', False)
        assert_key(client, 'legacy-bupt', False)
        if key == 'shared-rotated':
            assert_key(client, 'shared-first', False)
        Config.ROUTE_API_KEY = ''
        Config.load()
        assert_key(client, key, True)
        assert client.get('/compat/master/settings', headers={'Authorization': 'Bearer ' + key}).status_code == 401
        assert client.get('/compat/bupt/settings', headers={'Authorization': 'Bearer ' + key}).status_code == 401
    assert client.post('/compat/master/settings', headers=headers, json={'ROUTE_API_KEY': ''}).status_code == 200
    assert client.post('/predict', headers={'Authorization': 'Bearer legacy-master'}, json={'text': '', 'query': ''}).status_code == 400
    assert client.post('/route', headers={'X-API-Key': 'legacy-bupt'}, json={'text': '', 'query': ''}).status_code == 400
    assert_key(client, 'shared-rotated', False)


def test_settings_requires_admin_and_invalid_key_is_atomic(client):
    assert client.post('/compat/master/settings', json={'ROUTE_API_KEY': 'attacker'}).status_code == 401
    headers = admin_headers(client)
    assert client.post('/compat/master/settings', headers=headers, json={'ROUTE_API_KEY': 'valid'}).status_code == 200
    before = Config.get_settings_path().read_bytes()
    for value in [None, 123, 'bad\nkey', 'bad key']:
        assert client.post('/compat/master/settings', headers=headers, json={'ROUTE_API_KEY': value}).status_code == 400
        assert Config.ROUTE_API_KEY == 'valid'
        assert Config.get_settings_path().read_bytes() == before
    from intent_hub.services.log_service import redact_runtime
    assert redact_runtime('key=valid') == 'key=[REDACTED]'
