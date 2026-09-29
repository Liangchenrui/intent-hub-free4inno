# Intent Hub

Intent Hub is a single-workspace intent-routing service with a Flask backend and Vue 3 administration UI.

## Authentication

- Administrators sign in with username and password at `POST /auth/login`. The returned short-lived API key protects management APIs.
- Configure `ROUTE_API_KEY` in Settings for `POST /route`; if empty, it falls back to `AUTH_CODE`. The route key does not grant management access.

## Main APIs

- Routes: `/routes`, `/routes/search`, `/routes/{id}`
- Indexing: automatic route sync, `/reindex`, `/reindex/sync-route`, `/sync-tasks`
- Diagnostics: `/diagnostics/*`
- Settings: `/settings`
- Upstreams: configure and pull individual sources in Settings; route keys use `upstream-name.original-id`. See [multiple upstreams and migration](docs/changes/multiple-upstreams/README.md).
- Upstream integration contract: [fixed Agent pull API protocol](docs/api/upstream-agent-protocol.md), including list/detail endpoints, pagination, resource fields and response examples.
- Routing: `POST /route` — [API documentation](docs/api/routing-api.md)

Routing accepts `query`, optional `collection`, `upstream_id`, and `learn_from_fallback` (default true). Collection and upstream filters combine with AND across semantic search, negative filtering and LLM fallback. Responses contain `success/data/error`, with stable Agent IDs and route keys. The old prediction and compatibility routing paths are removed; use `/route` regardless of management API profile.

Collection selection is request-local and read-only: it does not create a collection or change settings. The selected collection must use the service's current embedding model/dimensions and route IDs from the local SQLite catalog; it is not an independent external Agent catalog. Automatic fallback learning is disabled when querying a collection other than the configured default.

Runtime data is stored directly in `intent-hub-backend/data/`: `routes.sqlite3`, `settings.json`, and `diagnostics_cache.json`.

```bash
pytest intent-hub-backend/tests -q
cd intent-hub-frontend && npm install && npm run build
```


## Unified master / BUPT version

Management compatibility APIs share one SQLite repository and sync queue. Routing has one independent `/route` endpoint. Set `API_COMPAT_PROFILE=master` (default) or `bupt` for root API aliases; `/compat/master/*` and `/compat/bupt/*` remain explicit. The administration UI uses the master namespace on either profile and current local credentials `admin / 123456`; it does not use a `DEFAULT_PASSWORD` environment variable. Configure the shared Route API Key in Settings for routing; BUPT management APIs still require environment `AUTH_CODE`. The LLM API key and shared routing key are configured in Settings and saved locally; other provider keys remain environment-only.

For populated installations, use the [migration and compatibility guide](docs/changes/branch-unification/README.md). Do not reuse a BUPT index without rebuilding against migrated internal IDs. Deployment is deferred by user request.

Successful LLM fallback adds the trimmed request to the selected Agent and queues vector synchronization. The test page disables automatic learning and uses explicit thumbs-up/down feedback. See [fallback learning](docs/changes/fallback-learning/README.md), [route API keys](docs/changes/route-api-key/README.md), and [delivery status and remaining work](docs/changes/2026-09-28-closeout.md).
