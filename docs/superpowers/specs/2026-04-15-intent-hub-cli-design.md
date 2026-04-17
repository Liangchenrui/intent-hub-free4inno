# Intent Hub CLI Lightweight Package Design

## Goal

Create a new lightweight standalone package `intent-hub-cli` for end users who need:

1. A local CLI command that talks to a remotely deployed Intent Hub backend
2. A minimal Python SDK for the same remote API

The new package must avoid backend-only dependencies and must be installable independently from the Flask server package.

## Scope

In scope:

1. Add a new package directory `intent-hub-cli/`
2. Expose CLI commands `intent-hub` and `intenthub`
3. Expose Python SDK class `IntentHubClient`
4. Support commands:
   - `login`
   - `whoami`
   - `route`
   - `dispatch`
   - `skills scan`
   - `skills apply`
5. Keep the client operating purely through remote HTTP APIs
6. Update user-facing docs to install and use the new package

Out of scope:

1. Publishing to PyPI
2. Building native executables
3. Changing backend API behavior
4. Large-scale refactors of unrelated backend modules

## Current State

The repository currently keeps CLI and client logic inside the backend package:

1. `intent-hub-backend/intent_hub/cli.py`
2. `intent-hub-backend/intent_hub/client.py`

This works functionally because the CLI already calls remote APIs, but distribution is wrong for end users because the backend package declares server and ML dependencies such as Flask, Qdrant, NumPy, UMAP, and LangChain.

## Recommended Approach

Create a separate package directory `intent-hub-cli/` with its own `pyproject.toml` and its own import namespace `intent_hub_cli`.

This approach is preferred because:

1. It gives the client package a clean dependency boundary
2. It keeps future PyPI publishing straightforward
3. It avoids re-coupling client code to server internals
4. It keeps migration risk low by copying a small, stable client surface instead of restructuring the whole backend package first

## Package Layout

Planned structure:

```text
intent-hub/
  intent-hub-backend/
    ...
  intent-hub-cli/
    pyproject.toml
    README.md
    intent_hub_cli/
      __init__.py
      cli.py
      client.py
    tests/
      test_cli.py
      test_client.py
```

## Public Interface

### CLI

The new package will install two console scripts:

1. `intent-hub`
2. `intenthub`

Supported commands:

1. `intent-hub login --endpoint <url> --code <access_code>`
2. `intent-hub whoami`
3. `intent-hub route "<text>" [--json]`
4. `intent-hub dispatch "<text>" [--json]`
5. `intent-hub skills scan`
6. `intent-hub skills apply --draft-file <path>`

### SDK

The package will export:

```python
from intent_hub_cli import IntentHubClient
```

`IntentHubClient` will keep the current minimal interface:

1. `whoami()`
2. `route(text)`
3. `dispatch(text)`
4. `skills_scan()`
5. `skills_apply(draft_file)`

## Dependency Policy

The new package should depend only on lightweight client-side runtime needs.

Required runtime dependency:

1. `requests>=2.31.0`

Explicitly excluded from the client package:

1. `flask`
2. `flask-compress`
3. `qdrant-client`
4. `numpy`
5. `scipy`
6. `numba`
7. `umap-learn`
8. `langchain-*`
9. any local embedding or server-only dependency

## Configuration Behavior

The CLI will preserve current login behavior to minimize migration risk:

1. Persist config at `~/.intent-hub/config.json`
2. Store:
   - `endpoint`
   - `access_code`
3. Reuse the saved config for later commands

No token exchange or local server state is introduced in this phase.

## Migration Strategy

Migration will be handled in two stages.

### Stage 1: Introduce standalone client package

1. Copy the existing remote client behavior into `intent-hub-cli`
2. Add tests for SDK and CLI behavior
3. Update docs to recommend the new package for end users

### Stage 2: Handle backend-package compatibility

For this change set, the backend package will remain functional. The old backend-embedded CLI can stay temporarily to avoid breaking local workflows during transition.

Documentation will clearly mark the new package as the preferred installation path for remote users.

Removal of the backend-embedded CLI, if desired, should happen in a later focused change after confirming no required internal workflow depends on it.

## Error Handling

The client package should preserve the current simple behavior:

1. HTTP failures raise request exceptions from `requests`
2. Missing login config raises a clear local error telling the user to run `intent-hub login`
3. JSON output remains machine-readable for `--json` use cases

No custom retry or advanced error translation is added in this phase.

## Testing Strategy

The implementation will follow TDD and verify both SDK and CLI behavior.

Test coverage required:

1. SDK sends requests to the configured endpoint with `Authorization: Bearer <access_code>`
2. `whoami`, `route`, `dispatch`, `skills_scan`, and `skills_apply` call the expected paths
3. CLI `login` writes config to the expected location
4. CLI commands load saved config and delegate to the SDK
5. Non-JSON CLI mode prints `route_key`
6. JSON CLI mode prints serialized payload
7. Running a command before `login` fails with a clear message

Tests should avoid real network calls by mocking the HTTP session boundary in the client package.

## Documentation Changes

Documentation must be updated to reflect the new preferred installation path:

1. Root `README.md`
2. Root `README.zh-CN.md`
3. Root `USER_GUIDE.md`
4. If needed, `intent-hub-cli/README.md`

The docs should distinguish:

1. Backend/server deployment
2. End-user CLI installation
3. Python SDK usage from the standalone client package

## Risks and Tradeoffs

### Temporary duplicate code

There will be short-term duplication between:

1. `intent-hub-backend/intent_hub/client.py`
2. `intent-hub-cli/intent_hub_cli/client.py`

This is acceptable for now because the duplicated surface is small and stable, and it keeps package boundaries clean.

### Compatibility drift

If backend APIs change later, both client copies could drift.

Mitigation:

1. Keep the standalone client surface small
2. Add focused tests around API paths and payloads
3. Prefer a later shared-contract refactor only if duplication becomes a real maintenance cost

## Success Criteria

The design is successful when all of the following are true:

1. A user can install only `intent-hub-cli` and use `intent-hub` against a remote backend
2. Installing `intent-hub-cli` does not install backend/server ML dependencies
3. Python callers can import `IntentHubClient` from the new package
4. Existing backend deployment behavior is unchanged
5. Repository docs point new users to the standalone package as the default client installation path
