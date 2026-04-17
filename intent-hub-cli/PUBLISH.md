# Publishing `intent-hub-cli`

This package is designed to be released independently from the backend package.

## Prerequisites

- PyPI project created: `intent-hub-cli`
- TestPyPI project created: `intent-hub-cli`
- Repository secrets configured:
  - `PYPI_TOKEN`
  - `TEST_PYPI_TOKEN`

Both tokens should be scoped to the `intent-hub-cli` project and stored as API tokens.

## Local Release Check

Run this before any upload:

```bash
cd intent-hub-cli
python -m pip install -e .[dev]
pytest tests -q
python -m build
python -m twine check dist/*
```

## Upload To TestPyPI

Use TestPyPI first for a dry run of the release artifact:

```bash
cd intent-hub-cli
python -m twine upload \
  --repository-url https://test.pypi.org/legacy/ \
  -u __token__ \
  -p <TEST_PYPI_TOKEN> \
  dist/*
```

Then verify installation from TestPyPI:

```bash
pip install \
  --index-url https://test.pypi.org/simple/ \
  --extra-index-url https://pypi.org/simple \
  intent-hub-cli
```

## Upload To PyPI

After TestPyPI verification passes:

```bash
cd intent-hub-cli
python -m twine upload \
  -u __token__ \
  -p <PYPI_TOKEN> \
  dist/*
```

Users can then install the package with:

```bash
pip install intent-hub-cli
```

## GitHub Actions Release

This repository includes `.github/workflows/publish-intent-hub-cli.yml`.

Supported triggers:

- Push tag: `intent-hub-cli-v*`
- Manual dispatch with target repository:
  - `testpypi`
  - `pypi`

Recommended release flow:

1. Bump `intent-hub-cli/pyproject.toml` version.
2. Run the local release check.
3. Push a tag like `intent-hub-cli-v0.1.0` to publish to PyPI.
4. Or run the workflow manually against `testpypi` before the final PyPI release.
