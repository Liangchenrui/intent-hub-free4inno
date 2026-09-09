from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.services.collection_service import CollectionService
from intent_hub.services.health_service import check_external_services


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_backend_secret_defaults_come_from_environment_without_literals():
    source = (REPO_ROOT / "intent-hub-backend" / "intent_hub" / "config.py").read_text(
        encoding="utf-8"
    )

    for name in ("AGENT_API_TOKEN", "QDRANT_API_KEY", "LLM_API_KEY", "AUTH_CODE"):
        assert f'os.getenv("{name}")' in source
        assert not re.search(rf'^\s*{name}\s*=\s*["\'][^"\']+["\']', source, re.MULTILINE)


def test_missing_auth_code_always_rejects_requests(monkeypatch):
    monkeypatch.setattr(Config, "AUTH_CODE", None)

    response = app.test_client().get("/agents")

    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "UNAUTHORIZED"


def test_missing_agent_api_token_fails_before_network(monkeypatch):
    class NoNetworkSession:
        def get(self, *args, **kwargs):
            raise AssertionError("network must not be called without an upstream token")

    monkeypatch.setattr(Config, "AGENT_API_TOKEN", None)

    with pytest.raises(RuntimeError, match="AGENT_API_TOKEN"):
        AgentSource(NoNetworkSession())._get("/resource/search")


@pytest.mark.parametrize("missing", [None, "", " \t"])
def test_component_manager_rejects_missing_qdrant_key_before_client_creation(
    missing, monkeypatch
):
    calls = []
    monkeypatch.setattr(Config, "QDRANT_API_KEY", missing)
    manager = ComponentManager(
        encoder_factory=lambda **kwargs: calls.append("encoder"),
        qdrant_client_factory=lambda **kwargs: calls.append("qdrant"),
        store=object(),
    )

    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        manager.create_qdrant("routes")

    assert calls == []


@pytest.mark.parametrize("missing", [None, "", " \t"])
def test_collection_client_rejects_missing_qdrant_key_before_creation(missing, monkeypatch):
    calls = []
    monkeypatch.setattr(Config, "QDRANT_API_KEY", missing)
    monkeypatch.setattr(
        "intent_hub.services.collection_service.QdrantClient",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        CollectionService._client()

    assert calls == []


@pytest.mark.parametrize("missing", [None, "", " \t"])
def test_health_check_rejects_missing_qdrant_key_before_any_probe(missing, monkeypatch):
    calls = []
    monkeypatch.setattr(Config, "QDRANT_API_KEY", missing)
    monkeypatch.setattr(
        "intent_hub.services.health_service._probe",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )

    with pytest.raises(RuntimeError, match="QDRANT_API_KEY"):
        check_external_services()

    assert calls == []


def test_legacy_settings_cannot_override_environment_secrets(tmp_path, monkeypatch):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text(
        json.dumps(
            {
                "QDRANT_API_KEY": "legacy-qdrant-value",
                "LLM_API_KEY": "legacy-llm-value",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(Config, "SETTINGS_FILE", settings_file)
    monkeypatch.setattr(Config, "QDRANT_API_KEY", "environment-qdrant-value")
    monkeypatch.setattr(Config, "LLM_API_KEY", "environment-llm-value")

    Config.load()

    assert Config.QDRANT_API_KEY == "environment-qdrant-value"
    assert Config.LLM_API_KEY == "environment-llm-value"

    Config.save({})
    persisted = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "QDRANT_API_KEY" not in persisted
    assert "LLM_API_KEY" not in persisted


@pytest.mark.parametrize("secret_name", ["QDRANT_API_KEY", "LLM_API_KEY"])
def test_runtime_settings_reject_and_never_persist_secret_fields(
    secret_name, tmp_path, monkeypatch
):
    settings_file = tmp_path / "settings.json"
    monkeypatch.setattr(Config, "SETTINGS_FILE", settings_file)

    assert secret_name not in Config.editable_keys()
    assert secret_name not in Config.to_dict()
    with pytest.raises(ValueError, match="不支持的设置项"):
        Config.save({secret_name: "request-supplied-secret"})
    assert not settings_file.exists()


def test_settings_api_never_exposes_or_accepts_secret_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "AUTH_CODE", "test-auth-code")
    monkeypatch.setattr(Config, "SETTINGS_FILE", tmp_path / "settings.json")
    headers = {"Authorization": "Bearer test-auth-code"}
    client = app.test_client()

    exposed = client.get("/settings", headers=headers)
    rejected = client.post(
        "/settings",
        headers=headers,
        json={"QDRANT_API_KEY": "request-supplied-secret", "LLM_API_KEY": "request-supplied-secret"},
    )

    assert exposed.status_code == 200
    assert "QDRANT_API_KEY" not in exposed.get_json()
    assert "LLM_API_KEY" not in exposed.get_json()
    assert rejected.status_code == 400
    assert not Config.SETTINGS_FILE.exists()


def test_frontend_delegates_authorization_to_nginx_template():
    api_source = (REPO_ROOT / "intent-hub-frontend" / "src" / "api" / "index.ts").read_text(
        encoding="utf-8"
    )
    template = (REPO_ROOT / "intent-hub-frontend" / "nginx.conf.template").read_text(
        encoding="utf-8"
    )
    dockerfile = (REPO_ROOT / "intent-hub-frontend" / "Dockerfile").read_text(encoding="utf-8")
    settings_view = (
        REPO_ROOT / "intent-hub-frontend" / "src" / "views" / "Settings.vue"
    ).read_text(encoding="utf-8")

    for secret_name in ("AUTH_CODE", "QDRANT_API_KEY", "LLM_API_KEY"):
        assert secret_name not in api_source
        assert secret_name not in settings_view
    assert "headers.Authorization" not in api_source
    assert "interceptors.request" not in api_source
    assert 'proxy_set_header Authorization "Bearer ${INTENT_HUB_AUTH_CODE}";' in template
    assert "nginx.conf.template /etc/nginx/templates/default.conf.template" in dockerfile


def test_compose_and_environment_example_inject_only_placeholder_secrets():
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env_lines = {
        line.split("=", 1)[0]: line.split("=", 1)[1]
        for line in (REPO_ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    }

    assert "AGENT_API_TOKEN=${AGENT_API_TOKEN:?" in compose
    assert "QDRANT_API_KEY=${QDRANT_API_KEY:?" in compose
    assert "LLM_API_KEY=${LLM_API_KEY:?" in compose
    assert "AUTH_CODE=${INTENT_HUB_AUTH_CODE:?" in compose
    assert "INTENT_HUB_AUTH_CODE=${INTENT_HUB_AUTH_CODE:?" in compose
    for name in (
        "AGENT_API_TOKEN",
        "QDRANT_API_KEY",
        "LLM_API_KEY",
        "INTENT_HUB_AUTH_CODE",
    ):
        assert env_lines[name].startswith("replace-with-")
