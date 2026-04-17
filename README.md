# Intent Hub

Intent Hub is a multi-tenant intent routing service. It combines a Flask backend, a Vue admin frontend, and a standalone CLI/SDK package for remote access.

**[English](README.md)** | **[中文](README.zh-CN.md)**

## What Is In This Repo

- `intent-hub-backend/`: backend service package
- `intent-hub-frontend/`: admin UI
- `intent-hub-cli/`: standalone CLI and Python SDK package
- `docs/`: shared project documentation

The backend currently exposes three API layers:

- Runtime APIs for tenants: `/v1/me`, `/v1/route`, `/v1/dispatch`
- Tenant control-plane APIs: `/tenant/*`
- Platform admin APIs: `/admin/*`

The old single-tenant endpoints such as `/routes`, `/settings`, `/diagnostics/*`, `/reindex`, and `/predict` still exist for compatibility, but the current project structure and documentation are centered on the multi-tenant API surface.

## Quick Start

For normal users, use the hosted service directly:

- Web entry: `http://intenthub.free4inno.com/`

If you need the remote CLI or Python SDK, install:

```bash
pip install intent-hub-cli==0.1.0
```

Skill scanning for end users is client-side:

- CLI and Python SDK scan local absolute or relative directories on the user's machine, collect `SKILL.md`, and upload the contents to the backend.
- The Web tenant page asks the browser to select a local directory and uploads discovered `SKILL.md` files.
- The backend no longer assumes a tenant can point at a filesystem path on the deployment host for routine skill scanning.

## Local Development

### Backend

```bash
cd intent-hub-backend
pip install -e .[dev]
python run.py
```

### Frontend

```bash
cd intent-hub-frontend
npm install
npm run dev
```

### Standalone CLI Package

Use the standalone package if you only need to call a remote Intent Hub deployment:

```bash
pip install intent-hub-cli==0.1.0
```

Example local scan:

```bash
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
```

## Runtime Data Layout

Backend runtime data is stored under `intent-hub-backend/data/`.

Important paths:

- `platform/tenants.json`: tenant metadata and access code records
- `platform/admin_settings.json`: platform admin settings
- `tenants/<tenant_id>/routes.json`: tenant routes
- `tenants/<tenant_id>/settings.json`: tenant settings
- `tenants/<tenant_id>/diagnostics_cache.json`: diagnostics cache
- `tenants/<tenant_id>/skills_index.json`: scanned skill index
- `tenants/<tenant_id>/imports/`: imported skill drafts

Legacy single-tenant files such as `routes.json` and `settings.json` may still exist for compatibility or migration, but tenant-scoped files are the current source of truth.

## Key Docs

- `USER_GUIDE.md`: operator-facing usage guide
- `docs/API.md`: API map and authentication model
- `docs/ARCHITECTURE.md`: code layout, runtime layout, and compatibility notes
- `intent-hub-cli/README.md`: CLI/SDK package usage
- `intent-hub-cli/PUBLISH.md`: standalone package release flow

## Project Layout

```text
intent-hub/
├── docs/
├── intent-hub-backend/
│   ├── intent_hub/
│   ├── data/
│   └── tests/
├── intent-hub-cli/
│   ├── intent_hub_cli/
│   └── tests/
├── intent-hub-frontend/
│   ├── public/
│   └── src/
├── AGENT.md
├── README.md
├── README.zh-CN.md
└── USER_GUIDE.md
```

## License

MIT. See `LICENSE`.
