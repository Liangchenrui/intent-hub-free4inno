# intent-hub-cli

Lightweight CLI and Python SDK for remote Intent Hub deployments.

## Install

If you want to use the published CLI or Python SDK, install the released package:

```bash
pip install intent-hub-cli==0.1.0
```

Editable install for package development:

```bash
cd intent-hub-cli
pip install -e .
```

Build and install a wheel:

```bash
cd intent-hub-cli
python -m pip install -U build
python -m build
pip install dist/intent_hub_cli-0.1.0-py3-none-any.whl
```

This produces:

- `dist/intent_hub_cli-0.1.0-py3-none-any.whl`
- `dist/intent_hub_cli-0.1.0.tar.gz`

After publishing:

```bash
pip install intent-hub-cli==0.1.0
```

## Publishing

Release validation:

```bash
cd intent-hub-cli
python -m pip install -e .[dev]
pytest tests -q
python -m build
python -m twine check dist/*
```

Manual upload to PyPI:

```bash
python -m twine upload -u __token__ -p <PYPI_TOKEN> dist/*
```

Manual upload to TestPyPI:

```bash
python -m twine upload \
  --repository-url https://test.pypi.org/legacy/ \
  -u __token__ \
  -p <TEST_PYPI_TOKEN> \
  dist/*
```

See `PUBLISH.md` for the full release flow. The repository also contains the GitHub Actions workflow for tag-based publishing.

## Usage

### CLI

```bash
intent-hub login --endpoint https://api.example.com --code <access_code>
intent-hub whoami
intent-hub route "help me organize a wiki"
intent-hub route "help me organize a wiki" --json
intent-hub dispatch "help me organize a wiki"
intent-hub dispatch "help me organize a wiki" --json
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
intent-hub skills apply --draft-file /path/to/draft.json
```

`intenthub` is available as an alias.

### Python SDK

```python
from intent_hub_cli import IntentHubClient

client = IntentHubClient(
    endpoint="https://api.example.com",
    access_code="ih_live_team_alpha_xxx",
)

print(client.whoami())
print(client.route("help me organize a wiki"))
print(client.dispatch("help me organize a wiki"))
scan_result = client.skills_scan_uploaded(
    source_id=None,
    source_label="team-skills",
    client_path_hint="./skills",
    skills=[
        {
            "relative_path": "wiki-builder/SKILL.md",
            "content": "# wiki-builder\n...",
        }
    ],
)
print(scan_result)
print(client.skills_apply("draft.json"))
```

## Configuration

The CLI stores credentials at `~/.intent-hub/config.json`:

```json
{
  "endpoint": "https://api.example.com",
  "access_code": "ih_live_team_alpha_xxx"
}
```

## Notes

- Dependency footprint is intentionally small: `requests>=2.31.0`
- This package does not ship backend dependencies such as Flask or Qdrant client
- Use this package for remote access; use `intent-hub-backend` when you are running or developing the server itself
- Skill scanning runs against the user's local directories and uploads `SKILL.md` content to the backend
