from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pytest_cleanup import cleanup_pytest_artifacts


@pytest.fixture(autouse=True)
def isolate_runtime_logs(monkeypatch, tmp_path):
    """Application log handlers must never write test records into the local workspace."""
    from intent_hub.config import Config
    monkeypatch.setattr(Config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(Config, "LLM_API_KEY", "offline-test-key")


def pytest_sessionfinish(session, exitstatus):
    cleanup_pytest_artifacts(REPO_ROOT)
