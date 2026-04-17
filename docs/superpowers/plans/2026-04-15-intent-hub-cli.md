# Intent Hub CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a standalone lightweight `intent-hub-cli` package that ships the remote CLI and Python SDK without backend/server dependencies.

**Architecture:** Keep the new package isolated under `intent-hub-cli/` with a dedicated Python package namespace `intent_hub_cli`. Recreate the current remote-only client behavior in the new package, add focused tests around HTTP calls and CLI config handling, and update repository docs to point end users to the standalone package.

**Tech Stack:** Python 3.9+, setuptools, requests, pytest

---

## File Map

- Create: `intent-hub-cli/pyproject.toml`
- Create: `intent-hub-cli/README.md`
- Create: `intent-hub-cli/intent_hub_cli/__init__.py`
- Create: `intent-hub-cli/intent_hub_cli/client.py`
- Create: `intent-hub-cli/intent_hub_cli/cli.py`
- Create: `intent-hub-cli/tests/test_client.py`
- Create: `intent-hub-cli/tests/test_cli.py`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `USER_GUIDE.md`

### Task 1: Scaffold the standalone package metadata

**Files:**
- Create: `intent-hub-cli/pyproject.toml`
- Create: `intent-hub-cli/README.md`
- Create: `intent-hub-cli/intent_hub_cli/__init__.py`

- [ ] **Step 1: Write the failing package metadata test**

Create `intent-hub-cli/tests/test_package_layout.py`:

```python
from pathlib import Path


def test_package_metadata_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pyproject.toml").exists()
    assert (root / "README.md").exists()
    assert (root / "intent_hub_cli" / "__init__.py").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest intent-hub-cli/tests/test_package_layout.py -v`
Expected: FAIL because the package files do not exist yet

- [ ] **Step 3: Write minimal package metadata**

Create `intent-hub-cli/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "intent-hub-cli"
version = "0.1.0"
description = "Lightweight CLI and SDK for remote Intent Hub APIs"
readme = "README.md"
requires-python = ">=3.9"
license = {text = "MIT"}
dependencies = [
    "requests>=2.31.0",
]

[project.scripts]
intent-hub = "intent_hub_cli.cli:main"
intenthub = "intent_hub_cli.cli:main"

[tool.setuptools.packages.find]
include = ["intent_hub_cli*"]
```

Create `intent-hub-cli/README.md`:

```md
# intent-hub-cli

Lightweight CLI and Python SDK for remote Intent Hub deployments.
```

Create `intent-hub-cli/intent_hub_cli/__init__.py`:

```python
from intent_hub_cli.client import IntentHubClient

__all__ = ["IntentHubClient"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest intent-hub-cli/tests/test_package_layout.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-cli/pyproject.toml intent-hub-cli/README.md intent-hub-cli/intent_hub_cli/__init__.py intent-hub-cli/tests/test_package_layout.py
git commit -m "feat: scaffold standalone intent-hub-cli package"
```

### Task 2: Add the failing SDK tests

**Files:**
- Create: `intent-hub-cli/tests/test_client.py`
- Test: `intent-hub-cli/intent_hub_cli/client.py`

- [ ] **Step 1: Write the failing SDK tests**

Create `intent-hub-cli/tests/test_client.py`:

```python
from types import SimpleNamespace

from intent_hub_cli import IntentHubClient


class DummySession:
    def __init__(self):
        self.calls = []

    def request(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"ok": True, "path": kwargs["url"]},
        )


def test_route_uses_bearer_auth_and_expected_path():
    session = DummySession()
    client = IntentHubClient("https://api.example.com/", "ih_live_test", session=session)

    payload = client.route("整理 wiki")

    assert payload["ok"] is True
    assert session.calls[0]["url"] == "https://api.example.com/v1/route"
    assert session.calls[0]["headers"]["Authorization"] == "Bearer ih_live_test"
    assert session.calls[0]["json"] == {"text": "整理 wiki"}


def test_skills_apply_posts_expected_payload():
    session = DummySession()
    client = IntentHubClient("https://api.example.com", "ih_live_test", session=session)

    client.skills_apply("draft.json")

    assert session.calls[0]["url"] == "https://api.example.com/tenant/skill-drafts/apply"
    assert session.calls[0]["json"] == {"draft_file": "draft.json"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest intent-hub-cli/tests/test_client.py -v`
Expected: FAIL with import error because `intent_hub_cli.client` does not exist yet

- [ ] **Step 3: Write minimal SDK implementation**

Create `intent-hub-cli/intent_hub_cli/client.py`:

```python
from __future__ import annotations

from typing import Any

import requests


class IntentHubClient:
    def __init__(self, endpoint: str, access_code: str, session: requests.Session | None = None):
        self.endpoint = endpoint.rstrip("/")
        self.access_code = access_code
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_code}",
            "Content-Type": "application/json",
        }

    def whoami(self) -> dict[str, Any]:
        return self._request("GET", "/v1/me")

    def route(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/v1/route", json={"text": text})

    def dispatch(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/v1/dispatch", json={"text": text})

    def skills_scan(self) -> dict[str, Any]:
        return self._request("POST", "/tenant/skill-sources/scan")

    def skills_apply(self, draft_file: str) -> dict[str, Any]:
        return self._request("POST", "/tenant/skill-drafts/apply", json={"draft_file": draft_file})

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = self.session.request(
            method=method,
            url=f"{self.endpoint}{path}",
            headers=self._headers,
            timeout=30,
            **kwargs,
        )
        response.raise_for_status()
        return response.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest intent-hub-cli/tests/test_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-cli/intent_hub_cli/client.py intent-hub-cli/tests/test_client.py
git commit -m "feat: add standalone intent-hub client sdk"
```

### Task 3: Add the failing CLI tests

**Files:**
- Create: `intent-hub-cli/tests/test_cli.py`
- Test: `intent-hub-cli/intent_hub_cli/cli.py`

- [ ] **Step 1: Write the failing CLI tests**

Create `intent-hub-cli/tests/test_cli.py`:

```python
import json

import pytest

from intent_hub_cli.cli import main


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

    def skills_scan(self):
        return {"discovered": 2}

    def skills_apply(self, draft_file: str):
        return {"created": 1, "draft_file": draft_file}


def test_login_writes_config(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)

    exit_code = main(["login", "--endpoint", "https://api.example.com", "--code", "ih_live_team_alpha"])

    assert exit_code == 0
    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["endpoint"] == "https://api.example.com"
    assert saved["access_code"] == "ih_live_team_alpha"
    assert "Saved login config" in capsys.readouterr().out


def test_route_prints_route_key_in_default_mode(tmp_path, monkeypatch, capsys):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"endpoint": "https://api.example.com", "access_code": "ih_live_team_alpha"}), encoding="utf-8")
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)
    monkeypatch.setattr("intent_hub_cli.cli.IntentHubClient", DummyClient)

    exit_code = main(["route", "整理 wiki"])

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == "wiki.builder"


def test_command_requires_login_config(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr("intent_hub_cli.cli.get_config_path", lambda: config_path)

    with pytest.raises(ValueError, match="Not logged in"):
        main(["whoami"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest intent-hub-cli/tests/test_cli.py -v`
Expected: FAIL because `intent_hub_cli.cli` does not exist yet

- [ ] **Step 3: Write minimal CLI implementation**

Create `intent-hub-cli/intent_hub_cli/cli.py`:

```python
from __future__ import annotations

import argparse
import json
from pathlib import Path

from intent_hub_cli.client import IntentHubClient


def get_config_path() -> Path:
    return Path.home() / ".intent-hub" / "config.json"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        raise ValueError("Not logged in. Run `intent-hub login --endpoint ... --code ...` first.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(endpoint: str, access_code: str) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"endpoint": endpoint, "access_code": access_code}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="intent-hub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login")
    login_parser.add_argument("--endpoint", required=True)
    login_parser.add_argument("--code", required=True)

    subparsers.add_parser("whoami")

    route_parser = subparsers.add_parser("route")
    route_parser.add_argument("text")
    route_parser.add_argument("--json", action="store_true", dest="json_output")

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("text")
    dispatch_parser.add_argument("--json", action="store_true", dest="json_output")

    skills_parser = subparsers.add_parser("skills")
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command", required=True)
    skills_subparsers.add_parser("scan")
    apply_parser = skills_subparsers.add_parser("apply")
    apply_parser.add_argument("--draft-file", required=True)

    return parser


def _client_from_config() -> IntentHubClient:
    config = load_config()
    return IntentHubClient(endpoint=config["endpoint"], access_code=config["access_code"])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "login":
        save_config(endpoint=args.endpoint, access_code=args.code)
        print("Saved login config")
        return 0

    client = _client_from_config()

    if args.command == "whoami":
        print(json.dumps(client.whoami(), ensure_ascii=False))
        return 0

    if args.command == "route":
        payload = client.route(args.text)
        print(json.dumps(payload, ensure_ascii=False) if args.json_output else payload.get("route_key", ""))
        return 0

    if args.command == "dispatch":
        payload = client.dispatch(args.text)
        print(json.dumps(payload, ensure_ascii=False) if args.json_output else payload.get("route_key", ""))
        return 0

    if args.command == "skills" and args.skills_command == "scan":
        print(json.dumps(client.skills_scan(), ensure_ascii=False))
        return 0

    if args.command == "skills" and args.skills_command == "apply":
        print(json.dumps(client.skills_apply(args.draft_file), ensure_ascii=False))
        return 0

    parser.error("Unsupported command")
    return 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest intent-hub-cli/tests/test_cli.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-cli/intent_hub_cli/cli.py intent-hub-cli/tests/test_cli.py
git commit -m "feat: add standalone intent-hub cli"
```

### Task 4: Update end-user documentation

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `USER_GUIDE.md`
- Modify: `intent-hub-cli/README.md`

- [ ] **Step 1: Write the failing docs assertions**

Create `intent-hub-cli/tests/test_docs.py`:

```python
from pathlib import Path


def test_root_docs_reference_standalone_cli_package():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    user_guide = (repo_root / "USER_GUIDE.md").read_text(encoding="utf-8")
    assert "intent-hub-cli" in readme
    assert "intent-hub-cli" in user_guide
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest intent-hub-cli/tests/test_docs.py -v`
Expected: FAIL because the docs do not yet mention the new package

- [ ] **Step 3: Write minimal docs updates**

Update `README.md` to add:

```md
## Standalone CLI Package

End users who only need the CLI or Python SDK for a remote Intent Hub deployment should install the standalone `intent-hub-cli` package instead of the backend package.
```

Update `README.zh-CN.md` to add:

```md
## 独立 CLI 包

如果用户只需要连接远程部署的 Intent Hub 服务，应安装独立的 `intent-hub-cli` 包，而不是后端服务包。
```

Update `USER_GUIDE.md` to replace the backend install-first guidance with:

```md
先安装独立客户端包，然后登录远程服务：

```bash
pip install ./intent-hub-cli
intent-hub login --endpoint http://127.0.0.1:5000 --code <access_code>
```
```

Update `intent-hub-cli/README.md` to include:

```md
## Install

```bash
pip install .
```

## Usage

```bash
intent-hub login --endpoint https://api.example.com --code <access_code>
intenthub route "帮我整理 wiki"
```
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest intent-hub-cli/tests/test_docs.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add README.md README.zh-CN.md USER_GUIDE.md intent-hub-cli/README.md intent-hub-cli/tests/test_docs.py
git commit -m "docs: document standalone intent-hub-cli package"
```

### Task 5: Run final verification

**Files:**
- Verify only

- [ ] **Step 1: Run standalone package tests**

Run: `pytest intent-hub-cli/tests -q`
Expected: all tests PASS

- [ ] **Step 2: Run backend CLI regression test**

Run: `pytest intent-hub-backend/tests/test_cli.py -q`
Expected: PASS to confirm the new package work did not break existing backend-embedded CLI behavior

- [ ] **Step 3: Inspect installed dependency boundary**

Run: `Get-Content intent-hub-cli/pyproject.toml`
Expected: only lightweight runtime dependency `requests>=2.31.0`

- [ ] **Step 4: Commit verification-safe final state**

```bash
git add intent-hub-cli README.md README.zh-CN.md USER_GUIDE.md
git commit -m "feat: add standalone lightweight intent-hub-cli package"
```
