# Architecture

## Repository Layout

```text
intent-hub/
├── docs/
├── intent-hub-backend/
│   ├── intent_hub/
│   │   ├── api/
│   │   ├── core/
│   │   ├── platform/
│   │   ├── services/
│   │   ├── tenant/
│   │   └── utils/
│   ├── data/
│   └── tests/
├── intent-hub-cli/
│   ├── intent_hub_cli/
│   └── tests/
└── intent-hub-frontend/
    └── src/
```

## Runtime Model

- `intent-hub-backend/` is the service runtime and package entry for local/backend deployment.
- `intent-hub-cli/` is a separately distributable client package for remote access.
- `intent-hub-frontend/` is the admin UI that talks to the backend.

## Data Layout

The active multi-tenant runtime layout is:

```text
intent-hub-backend/data/
├── platform/
│   ├── admin_settings.json
│   └── tenants.json
└── tenants/
    └── <tenant_id>/
        ├── diagnostics_cache.json
        ├── imports/
        ├── routes.json
        ├── settings.json
        └── skills_index.json
```

Legacy top-level files such as `routes.json`, `settings.json`, and `diagnostics_cache.json` may still be present to support migration or compatibility paths.

## Compatibility Notes

- The current primary API surface is multi-tenant.
- The backend still ships single-tenant compatibility endpoints.
- `intent-hub-backend/pythonSDK.py` is kept as a compatibility example and points to the standalone `intent-hub-cli` package.
- Shared project documentation now lives at the repository root rather than `intent-hub-backend/docs/`.
