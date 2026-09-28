# Intent Hub

Intent Hub is a single-workspace intent-routing service with a Flask backend and Vue 3 administration UI.

## Authentication

- Administrators sign in with username and password at `POST /auth/login`. The returned short-lived API key protects management APIs.
- Set the shared `ROUTE_API_KEY` in Settings for `/predict` and `/route` (including compatibility paths). Saving takes effect immediately in the local process and persists across restarts. If empty, each contract uses its legacy environment key (`PREDICT_AUTH_KEY` / `AUTH_CODE`). The shared routing key does not grant management access.

## Main APIs

- Routes: `/routes`, `/routes/search`, `/routes/{id}`
- Indexing: automatic route sync, `/reindex`, `/reindex/sync-route`, `/sync-tasks`
- Diagnostics: `/diagnostics/*`
- Settings: `/settings`
- Prediction: `/predict`

Runtime data is stored directly in `intent-hub-backend/data/`: `routes.sqlite3`, `settings.json`, and `diagnostics_cache.json`.

```bash
pytest intent-hub-backend/tests -q
cd intent-hub-frontend && npm install && npm run build
```


## Unified master / BUPT version

Both contracts share one SQLite repository, routing core and sync queue. Set `API_COMPAT_PROFILE=master` (default) or `bupt` for root API aliases; `/compat/master/*` and `/compat/bupt/*` remain explicit. The administration UI uses the master namespace on either profile and current local credentials `admin / 123456`; it does not use a `DEFAULT_PASSWORD` environment variable. Configure the shared Route API Key in Settings for routing; BUPT management APIs still require environment `AUTH_CODE`. The LLM API key and shared routing key are configured in Settings and saved locally; other provider keys remain environment-only.

For populated installations, use the [migration and compatibility guide](docs/changes/branch-unification/README.md). Do not reuse a BUPT index without rebuilding against migrated internal IDs. Deployment is deferred by user request.

Successful LLM fallback adds the trimmed request to the selected Agent and queues vector synchronization. The test page disables automatic learning and uses explicit thumbs-up/down feedback. See [fallback learning](docs/changes/fallback-learning/README.md), [route API keys](docs/changes/route-api-key/README.md), and [delivery status and remaining work](docs/changes/2026-09-28-closeout.md).
