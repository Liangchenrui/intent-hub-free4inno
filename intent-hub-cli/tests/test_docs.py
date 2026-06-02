import re
from pathlib import Path


def _package_version() -> str:
    package_root = Path(__file__).resolve().parents[1]
    pyproject = (package_root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', pyproject, re.MULTILINE)
    assert match
    return match.group(1)


def test_root_docs_reference_standalone_cli_package():
    repo_root = Path(__file__).resolve().parents[2]
    readme = (repo_root / "README.md").read_text(encoding="utf-8")
    readme_zh = (repo_root / "README.zh-CN.md").read_text(encoding="utf-8")
    user_guide = (repo_root / "USER_GUIDE.md").read_text(encoding="utf-8")
    package_version = _package_version()
    install_command = f"pip install intent-hub-cli=={package_version}"

    assert "intent-hub-cli" in readme
    assert install_command in readme
    assert "intent-hub-cli" in readme_zh
    assert install_command in readme_zh
    assert "intent-hub-cli" in user_guide
    assert "python -m build" in user_guide
    assert install_command in user_guide
    assert "--source-path ./skills" in readme
    assert "浏览器目录选择器" in user_guide
    assert "用户本地" in readme_zh


def test_package_readme_describes_wheel_install_flow():
    package_root = Path(__file__).resolve().parents[1]
    package_readme = (package_root / "README.md").read_text(encoding="utf-8")
    package_version = _package_version()

    assert "python -m build" in package_readme
    assert "pip install dist/" in package_readme
    assert "pip install -e ." in package_readme
    assert "twine upload" in package_readme
    assert f"pip install intent-hub-cli=={package_version}" in package_readme
    assert f"dist/intent_hub_cli-{package_version}-py3-none-any.whl" in package_readme
    assert f"dist/intent_hub_cli-{package_version}.tar.gz" in package_readme
    assert "--source-path ./skills" in package_readme
    assert "skills_scan_uploaded" in package_readme


def test_publish_assets_exist_and_describe_pypi_release():
    repo_root = Path(__file__).resolve().parents[2]
    package_root = Path(__file__).resolve().parents[1]

    publish_guide = (package_root / "PUBLISH.md").read_text(encoding="utf-8")
    workflow = (repo_root / ".github" / "workflows" / "publish-intent-hub-cli.yml").read_text(encoding="utf-8")

    assert "PYPI_TOKEN" in publish_guide
    assert "TEST_PYPI_TOKEN" in publish_guide
    assert "python -m twine upload" in publish_guide
    assert "pypi" in workflow
    assert "workflow_dispatch" in workflow
    assert "refs/tags/intent-hub-cli-v" in workflow
