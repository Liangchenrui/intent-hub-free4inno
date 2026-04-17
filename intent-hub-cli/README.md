# intent-hub-cli

Lightweight CLI and Python SDK for remote Intent Hub deployments.

## Install

```bash
cd intent-hub-cli
pip install -e .
```

Alternatively, install from the repository root:

```bash
pip install ./intent-hub-cli
```

To build a distributable wheel and install it like a regular pip package:

```bash
cd intent-hub-cli
python -m pip install -U build
python -m build
pip install dist/intent_hub_cli-0.1.0-py3-none-any.whl
```

This produces both:

- `dist/intent_hub_cli-0.1.0-py3-none-any.whl`
- `dist/intent_hub_cli-0.1.0.tar.gz`

After the package is published to PyPI later, installation becomes:

```bash
pip install intent-hub-cli
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

The repository also includes a GitHub Actions workflow for tag-based and manual publishing.
See `PUBLISH.md` for the full release flow.

## Usage

### CLI

First, login to your remote Intent Hub instance:

```bash
intent-hub login --endpoint https://api.example.com --code <access_code>
```

Available commands:

```bash
# Check your identity
intent-hub whoami

# Route text to find the best matching intent
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json

# Dispatch text (returns route + dispatch suggestions)
intent-hub dispatch "帮我整理 wiki"
intent-hub dispatch "帮我整理 wiki" --json

# Scan for skills
intent-hub skills scan

# Apply a skill draft
intent-hub skills apply --draft-file /path/to/draft.json
```

The `intenthub` command is also available as an alias.

### Python SDK

```python
from intent_hub_cli import IntentHubClient

# Initialize client
client = IntentHubClient(
    endpoint="https://api.example.com",
    access_code="ih_live_team_alpha_xxx",
)

# Check identity
print(client.whoami())

# Route text
result = client.route("帮我整理 wiki")
print(result)

# Dispatch text
dispatch_result = client.dispatch("帮我整理 wiki")
print(dispatch_result)

# Scan skills
skills = client.skills_scan()
print(skills)

# Apply skill draft
client.skills_apply("draft.json")
```

## Configuration

The CLI stores login configuration at `~/.intent-hub/config.json`:

```json
{
  "endpoint": "https://api.example.com",
  "access_code": "ih_live_team_alpha_xxx"
}
```

## Development

### Running tests

```bash
cd intent-hub-cli
pytest tests/ -v
```

### Building distributions

```bash
cd intent-hub-cli
python -m pip install -e .[dev]
python -m build
python -m twine check dist/*
```

### Project structure

```text
intent-hub-cli/
├── pyproject.toml
├── README.md
├── intent_hub_cli/
│   ├── __init__.py
│   ├── cli.py
│   └── client.py
└── tests/
    ├── test_cli.py
    ├── test_client.py
    ├── test_package_layout.py
    └── test_docs.py
```

## Notes

- This package only depends on `requests>=2.31.0`
- It does not include backend server dependencies (Flask, Qdrant, NumPy, etc.)
- Use this package when you only need to interact with a remote Intent Hub API
- For local development or deployment, use the full `intent-hub-backend` package
