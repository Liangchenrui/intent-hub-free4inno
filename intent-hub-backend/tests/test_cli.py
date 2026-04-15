import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.cli import main


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


class DummyClient:
    def __init__(self, endpoint: str, access_code: str):
        self.endpoint = endpoint
        self.access_code = access_code

    def whoami(self):
        return {"tenant_id": "team_alpha", "collection": "intent_hub_team_alpha"}

    def route(self, text: str):
        return {"route_key": "wiki.builder", "text": text}

    def dispatch(self, text: str):
        return {"route_key": "wiki.builder", "dispatch": {"status": "not_executed"}, "text": text}

    def skills_scan(self):
        return {"discovered": 2}

    def skills_apply(self, draft_file: str):
        return {"created": 1, "draft_file": draft_file}


def test_cli_login_writes_config(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    monkeypatch.setattr("intent_hub.cli.get_config_path", lambda: config_path)

    exit_code = main(["login", "--endpoint", "http://127.0.0.1:5000", "--code", "ih_live_team_alpha"])

    assert exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["endpoint"] == "http://127.0.0.1:5000"
    assert saved["access_code"] == "ih_live_team_alpha"
    assert "Saved login config" in capsys.readouterr().out


def test_cli_route_uses_saved_config(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    config_path.write_text(
        json.dumps({"endpoint": "http://127.0.0.1:5000", "access_code": "ih_live_team_alpha"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("intent_hub.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub.cli.IntentHubClient", DummyClient)

    exit_code = main(["route", "整理 wiki", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["route_key"] == "wiki.builder"


def test_cli_skills_scan_and_apply(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    config_path.write_text(
        json.dumps({"endpoint": "http://127.0.0.1:5000", "access_code": "ih_live_team_alpha"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("intent_hub.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub.cli.IntentHubClient", DummyClient)

    scan_exit_code = main(["skills", "scan"])
    assert scan_exit_code == 0
    assert "discovered" in capsys.readouterr().out

    apply_exit_code = main(["skills", "apply", "--draft-file", "draft.json"])
    assert apply_exit_code == 0
    assert "created" in capsys.readouterr().out


def test_cli_dispatch_uses_saved_config(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    config_path.write_text(
        json.dumps({"endpoint": "http://127.0.0.1:5000", "access_code": "ih_live_team_alpha"}),
        encoding="utf-8",
    )
    monkeypatch.setattr("intent_hub.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub.cli.IntentHubClient", DummyClient)

    exit_code = main(["dispatch", "整理 wiki", "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["route_key"] == "wiki.builder"
    assert payload["dispatch"]["status"] == "not_executed"
