import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub_cli import cli


class DummyClient:
    def __init__(self, endpoint: str, access_code: str):
        self.endpoint = endpoint
        self.access_code = access_code

    def whoami(self):
        return {"tenant_id": "team_alpha"}

    def route(self, text: str):
        return {"route_key": "wiki.builder", "text": text}

    def dispatch(self, text: str):
        return {"route_key": "wiki.builder", "dispatch": {"status": "not_executed"}}

    def skills_scan_uploaded(self, **kwargs):
        return {
            "source_id": kwargs.get("source_id") or "src_001",
            "discovered": len(kwargs["skills"]),
            "uploaded": len(kwargs["skills"]),
            "updated": 1,
            "stale": 0,
            "applied": 0,
            "skipped": 0,
            "errors": [],
        }

    def skills_apply(self, draft_file: str):
        return {"created": 1, "draft_file": draft_file}


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def test_login_writes_config(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)

    exit_code = cli.main(["login", "--endpoint", "https://api.example.com", "--code", "ih_live_team_alpha"])

    assert exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["endpoint"] == "https://api.example.com"
    assert saved["access_code"] == "ih_live_team_alpha"
    assert "Saved login config" in capsys.readouterr().out


def test_route_prints_route_key_in_default_mode(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    config_path.write_text(json.dumps({"endpoint": "https://api.example.com", "access_code": "ih_live_team_alpha"}), encoding="utf-8")
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub_cli.cli.IntentHubClient", DummyClient)

    exit_code = cli.main(["route", "整理 wiki"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "wiki.builder"


def test_command_requires_login_config(test_dir, monkeypatch):
    config_path = test_dir / "config.json"
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)

    exit_code = cli.main(["whoami"])

    assert exit_code == 1


def test_dispatch_and_skills_commands_print_json(test_dir, monkeypatch, capsys):
    config_path = test_dir / "config.json"
    config_path.write_text(json.dumps({"endpoint": "https://api.example.com", "access_code": "ih_live_team_alpha"}), encoding="utf-8")
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub_cli.cli.IntentHubClient", DummyClient)
    skills_root = test_dir / "skills"
    (skills_root / "wiki_builder").mkdir(parents=True, exist_ok=True)
    (skills_root / "wiki_builder" / "SKILL.md").write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")

    dispatch_exit_code = cli.main(["dispatch", "整理 wiki", "--json"])
    assert dispatch_exit_code == 0
    dispatch_payload = json.loads(capsys.readouterr().out)
    assert dispatch_payload["route_key"] == "wiki.builder"
    assert dispatch_payload["dispatch"]["status"] == "not_executed"

    scan_exit_code = cli.main(["skills", "scan", "--source-path", str(skills_root), "--source-label", "My Local Skills"])
    assert scan_exit_code == 0
    scan_payload = json.loads(capsys.readouterr().out)
    assert scan_payload["discovered"] == 1
    assert scan_payload["source_id"] == "src_001"

    apply_exit_code = cli.main(["skills", "apply", "--draft-file", "draft.json"])
    assert apply_exit_code == 0
    apply_payload = json.loads(capsys.readouterr().out)
    assert apply_payload["created"] == 1
    assert apply_payload["draft_file"] == "draft.json"


def test_save_config_sets_secure_permissions_on_posix(test_dir, monkeypatch):
    config_path = test_dir / "config.json"
    chmod_calls = []

    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub_cli.cli.os.name", "posix")
    monkeypatch.setattr(Path, "chmod", lambda self, mode: chmod_calls.append((self, mode)))

    cli.save_config(endpoint="https://api.example.com", access_code="ih_live_team_alpha")

    assert chmod_calls == [(config_path, 0o600)]
