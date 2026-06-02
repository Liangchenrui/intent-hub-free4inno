# API

## Authentication

- Admin requests use `Authorization: Bearer <api_key>`.
- Tenant runtime and control-plane requests use `Authorization: Bearer <access_code>`.
- Compatibility endpoints keep their existing authentication behavior for backward compatibility.

## Route Index

The route list below is generated from `intent-hub-backend/intent_hub/app.py`.
Run `python -m scripts.api_docs update-api-md` after changing Flask routes, and run
`python -m scripts.api_docs check` before committing API changes.

<!-- BEGIN AUTO-GENERATED ROUTES -->
### Admin APIs

- `GET /admin/tenants`
- `POST /admin/tenants`
- `POST /admin/tenants/{tenant_id}/access-codes`
- `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/disable`
- `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate`
- `POST /auth/login`

### Tenant Runtime APIs

- `POST /v1/dispatch`
- `GET /v1/me`
- `POST /v1/route`

### Tenant Control-Plane APIs

- `POST /tenant/diagnostics/apply-repair`
- `GET /tenant/diagnostics/overlap`
- `GET /tenant/diagnostics/overlap/{route_id}`
- `POST /tenant/diagnostics/repair`
- `GET /tenant/diagnostics/umap`
- `POST /tenant/reindex`
- `POST /tenant/reindex/sync-route`
- `GET /tenant/routes`
- `POST /tenant/routes`
- `POST /tenant/routes/generate-utterances`
- `POST /tenant/routes/import`
- `POST /tenant/routes/import-skill`
- `GET /tenant/routes/search`
- `PUT /tenant/routes/{route_id}`
- `DELETE /tenant/routes/{route_id}`
- `POST /tenant/routes/{route_id}/feedback/negative`
- `DELETE /tenant/routes/{route_id}/feedback/negative`
- `POST /tenant/routes/{route_id}/feedback/positive`
- `DELETE /tenant/routes/{route_id}/feedback/positive`
- `POST /tenant/routes/{route_id}/negative-samples`
- `DELETE /tenant/routes/{route_id}/negative-samples`
- `GET /tenant/settings`
- `POST /tenant/settings`
- `GET /tenant/skill-drafts`
- `POST /tenant/skill-drafts/apply`
- `GET /tenant/skill-sources`
- `POST /tenant/skill-sources`
- `POST /tenant/skill-sources/scan`

### Compatibility Endpoints

- `POST /diagnostics/apply-repair`
- `GET /diagnostics/overlap`
- `GET /diagnostics/overlap/{route_id}`
- `POST /diagnostics/repair`
- `GET /diagnostics/umap`
- `POST /predict`
- `POST /reindex`
- `POST /reindex/sync-route`
- `GET /routes`
- `POST /routes`
- `POST /routes/generate-utterances`
- `POST /routes/import`
- `POST /routes/import-skill`
- `GET /routes/search`
- `PUT /routes/{route_id}`
- `DELETE /routes/{route_id}`
- `POST /routes/{route_id}/negative-samples`
- `DELETE /routes/{route_id}/negative-samples`
- `GET /settings`
- `POST /settings`
<!-- END AUTO-GENERATED ROUTES -->

New integrations should prefer `/v1/*`, `/tenant/*`, and `/admin/*`.
