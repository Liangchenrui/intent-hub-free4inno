"""配置模块测试"""
import json

import pytest

from intent_hub.config import Config
from intent_hub.auth import AuthManager


def test_config_defaults():
    """测试配置默认值"""
    assert Config.DEFAULT_ROUTE_ID == 0
    assert Config.DEFAULT_ROUTE_NAME == "none"
    assert Config.DEFAULT_ROUTE_KEY == "fallback.default"
    assert Config.BATCH_SIZE == 32
    assert Config.ROUTES_CONFIG_PATH.endswith("data\\routes.json") or Config.ROUTES_CONFIG_PATH.endswith("data/routes.json")
    assert Config.DEFAULT_USERNAME == "admin"
    assert Config.DEFAULT_PASSWORD == "telestar"


def test_management_login_uses_fixed_admin_telestar(monkeypatch):
    monkeypatch.setattr(Config, "DEFAULT_USERNAME", "admin")
    monkeypatch.setattr(Config, "DEFAULT_PASSWORD", "telestar")
    manager = AuthManager()

    assert manager.verify_user("admin", "telestar")
    assert not manager.verify_user("admin", "wrong-password")
    assert not manager.verify_user("other", "telestar")


def test_upstream_agent_settings_default_to_bupt_and_are_editable(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(Config, "SETTINGS_FILE_PATH", str(settings_path))
    monkeypatch.setattr(Config, "AGENT_API_URL", "https://yuanfang.bupt.edu.cn/ac/api")
    monkeypatch.setattr(Config, "AGENT_API_LABEL_IDS", "87,88,89")

    Config.save({
        "AGENT_API_URL": "https://agents.example/api/",
        "AGENT_API_LABEL_IDS": "101, 102,101",
    })

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert Config.AGENT_API_URL == "https://agents.example/api"
    assert Config.AGENT_API_LABEL_IDS == "101,102,101"
    assert saved["AGENT_API_URL"] == "https://agents.example/api"
    assert saved["AGENT_API_LABEL_IDS"] == "101,102,101"


def test_llm_api_key_is_saved_in_local_settings(monkeypatch, tmp_path):
    settings_path = tmp_path / "settings.json"
    monkeypatch.setattr(Config, "SETTINGS_FILE_PATH", str(settings_path))
    monkeypatch.setattr(Config, "LLM_API_KEY", None)

    Config.save({"LLM_API_KEY": "local-llm-key"})

    saved = json.loads(settings_path.read_text(encoding="utf-8"))
    assert Config.LLM_API_KEY == "local-llm-key"
    assert saved["LLM_API_KEY"] == "local-llm-key"
    assert Config.to_dict()["LLM_API_KEY"] == "local-llm-key"


@pytest.mark.parametrize("values", [
    {"AGENT_API_URL": "agents.example/api"},
    {"AGENT_API_LABEL_IDS": "87,not-a-label"},
])
def test_upstream_agent_settings_reject_invalid_values(monkeypatch, tmp_path, values):
    monkeypatch.setattr(Config, "SETTINGS_FILE_PATH", str(tmp_path / "settings.json"))
    with pytest.raises(ValueError):
        Config.save(values)
