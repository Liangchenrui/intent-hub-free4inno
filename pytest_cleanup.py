from __future__ import annotations

import shutil
from pathlib import Path
from typing import Iterable


PYTEST_DIR_NAMES = {".pytest_cache", "pytest"}

PYTEST_PREFIXES = (
    "pytest-",
    "pytest_cache-",
    "pytest-cache-",
    "pytest-of-",
)


def iter_pytest_artifacts(root: Path) -> Iterable[Path]:
    for path in root.rglob("*"):
        if not path.is_dir():
            continue
        if path.name in PYTEST_DIR_NAMES or path.name.startswith(PYTEST_PREFIXES):
            yield path


def cleanup_pytest_artifacts(root: Path) -> list[Path]:
    removed: list[Path] = []
    candidates = sorted(iter_pytest_artifacts(root), key=lambda item: len(item.parts), reverse=True)
    for path in candidates:
        if not path.exists():
            continue
        shutil.rmtree(path, ignore_errors=True)
        if not path.exists():
            removed.append(path)
    return removed
