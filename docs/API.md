# API

## Authentication

### Admin APIs

- `POST /auth/login`
- `GET /admin/tenants`
- `POST /admin/tenants`
- `POST /admin/tenants/<tenant_id>/access-codes`
- `POST /admin/tenants/<tenant_id>/access-codes/<code_id>/rotate`
- `POST /admin/tenants/<tenant_id>/access-codes/<code_id>/disable`

Admin requests use `Authorization: Bearer <api_key>`.

### Tenant Runtime APIs

- `GET /v1/me`
- `POST /v1/route`
- `POST /v1/dispatch`

Tenant runtime requests use `Authorization: Bearer <access_code>`.

### Tenant Control-Plane APIs

- `GET /tenant/skill-sources`
- `POST /tenant/skill-sources`
- `POST /tenant/skill-sources/scan`
- `GET /tenant/skill-drafts`
- `POST /tenant/skill-drafts/apply`
- `GET /tenant/routes`
- `GET /tenant/routes/search`
- `POST /tenant/routes`
- `PUT /tenant/routes/<route_id>`
- `DELETE /tenant/routes/<route_id>`
- `POST /tenant/routes/generate-utterances`
- `POST /tenant/routes/import-skill`
- `POST /tenant/routes/import`
- `POST /tenant/routes/<route_id>/negative-samples`
- `DELETE /tenant/routes/<route_id>/negative-samples`
- `POST /tenant/reindex`
- `POST /tenant/reindex/sync-route`
- `GET /tenant/diagnostics/overlap`
- `GET /tenant/diagnostics/overlap/<route_id>`
- `GET /tenant/diagnostics/umap`
- `POST /tenant/diagnostics/repair`
- `POST /tenant/diagnostics/apply-repair`
- `GET /tenant/settings`
- `POST /tenant/settings`

Tenant control-plane requests also use `Authorization: Bearer <access_code>`.

## Compatibility Endpoints

The backend still exposes single-tenant compatibility endpoints:

- `POST /predict`
- `/routes*`
- `/reindex*`
- `/diagnostics*`
- `/settings`

These are retained for backward compatibility. New integrations should prefer `/v1/*`, `/tenant/*`, and `/admin/*`.
