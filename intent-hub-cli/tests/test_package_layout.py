from pathlib import Path


def test_package_metadata_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pyproject.toml").exists()
    assert (root / "README.md").exists()
    assert (root / "intent_hub_cli" / "__init__.py").exists()
