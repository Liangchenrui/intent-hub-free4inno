from pathlib import Path


def test_python_sdk_example_uses_standalone_cli_package_import():
    repo_root = Path(__file__).resolve().parents[2]
    sdk_example = (repo_root / "intent-hub-backend" / "pythonSDK.py").read_text(encoding="utf-8")

    assert "from intent_hub_cli import IntentHubClient" in sdk_example
