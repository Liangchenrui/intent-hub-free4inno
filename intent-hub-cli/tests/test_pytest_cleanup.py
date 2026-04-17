from pathlib import Path
import shutil

from pytest_cleanup import cleanup_pytest_artifacts


def test_cleanup_pytest_artifacts_removes_only_pytest_directories():
    root = Path.cwd() / ".tmp" / "cleanup-test-root"
    shutil.rmtree(root, ignore_errors=True)
    try:
        removable = [
            root / ".pytest_cache",
            root / ".tmp" / "pytest",
            root / "pytest-cache-files-abc123",
            root / "nested" / "pytest-of-user",
        ]
        preserved = [
            root / "dist",
            root / "pytest_data",
            root / "nested" / "reports",
        ]

        for directory in removable + preserved:
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "marker.txt").write_text("x", encoding="utf-8")

        removed = cleanup_pytest_artifacts(root)
        removed_paths = {path.resolve() for path in removed}

        for directory in removable:
            assert not directory.exists()
            assert directory.resolve() in removed_paths

        for directory in preserved:
            assert directory.exists()
    finally:
        shutil.rmtree(root, ignore_errors=True)
