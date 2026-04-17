from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pytest_cleanup import cleanup_pytest_artifacts


def pytest_sessionfinish(session, exitstatus):
    cleanup_pytest_artifacts(REPO_ROOT)
