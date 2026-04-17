from pathlib import Path


def test_package_metadata_files_exist():
    root = Path(__file__).resolve().parents[1]
    assert (root / "pyproject.toml").exists()
    assert (root / "README.md").exists()
    assert (root / "intent_hub_cli" / "__init__.py").exists()


def test_pyproject_contains_distribution_metadata():
    root = Path(__file__).resolve().parents[1]
    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")

    assert 'name = "intent-hub-cli"' in pyproject
    assert '[project.urls]' in pyproject
    assert 'Homepage' in pyproject
    assert 'Repository' in pyproject
    assert 'Documentation' in pyproject
    assert 'classifiers = [' in pyproject
    assert 'license = "MIT"' in pyproject
    assert '"Programming Language :: Python :: 3"' in pyproject
    assert '"build>=' in pyproject
    assert '"twine>=' in pyproject
