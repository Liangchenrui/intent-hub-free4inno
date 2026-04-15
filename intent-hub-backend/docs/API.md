# Intent Hub API

## Runtime

### `GET /v1/me`

- Auth: `Authorization: Bearer <access_code>`
- Returns current tenant and access code identity.

### `POST /v1/route`

- Auth: `Authorization: Bearer <access_code>`
- Body:

```json
{
  "text": "帮我整理 wiki"
}
```

- Returns top route contract plus match list.

### `POST /v1/dispatch`

- Auth: `Authorization: Bearer <access_code>`
- Body:

```json
{
  "text": "帮我整理 wiki"
}
```

- Returns route contract + dispatch suggestion. Current MVP does not execute tools directly.

### `POST /predict`

- Auth:
  - tenant `access_code`
  - or legacy `PREDICT_AUTH_KEY`
  - or legacy admin API key when enabled
- Compatibility endpoint. Tenant access code will reuse tenant-scoped runtime chain.

## Platform Admin

### `GET /admin/tenants`

- Auth: admin API key
- Returns tenants and access code metadata without plaintext code values.

### `POST /admin/tenants`

- Auth: admin API key
- Body:

```json
{
  "tenant_id": "team_alpha",
  "name": "Team Alpha"
}
```

- Creates tenant and returns one plaintext initial `access_code`.

### `POST /admin/tenants/{tenant_id}/access-codes`

- Auth: admin API key
- Body:

```json
{
  "label": "cli"
}
```

### `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate`

- Auth: admin API key
- Returns newly generated plaintext `access_code`.

### `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/disable`

- Auth: admin API key

## Tenant Skill Control Plane

### `GET /tenant/skill-sources`

- Auth: tenant `access_code`

### `POST /tenant/skill-sources`

- Auth: tenant `access_code`
- Body:

```json
{
  "path": "D:/skills",
  "sync_mode": "draft",
  "enabled": true
}
```

### `POST /tenant/skill-sources/scan`

- Auth: tenant `access_code`
- Scans configured `SKILL.md` sources, generates JSON drafts, updates `skills_index.json`.

### `GET /tenant/skill-drafts`

- Auth: tenant `access_code`
- Returns draft index items from `skills_index.json`.

### `POST /tenant/skill-drafts/apply`

- Auth: tenant `access_code`
- Body:

```json
{
  "draft_file": "D:/.../imports/skills/src_001/wiki_builder.json"
}
```

- Imports one draft into tenant `routes.json`.

## Python SDK

```python
from intent_hub import IntentHubClient

client = IntentHubClient(
    endpoint="http://127.0.0.1:5000",
    access_code="ih_live_team_alpha_xxx",
)

print(client.whoami())
print(client.route("帮我整理 wiki"))
```

## CLI

```bash
intent-hub login --endpoint http://127.0.0.1:5000 --code ih_live_team_alpha_xxx
intent-hub whoami
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json
intent-hub dispatch "帮我整理 wiki"
intent-hub dispatch "帮我整理 wiki" --json
intent-hub skills scan
intent-hub skills apply --draft-file D:/.../wiki_builder.json
```
