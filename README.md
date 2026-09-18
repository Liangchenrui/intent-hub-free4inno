# Intent Hub

Intent Hub is a single-workspace intent-routing service with a Flask backend and Vue 3 administration UI.

## Authentication

- Administrators sign in with username and password at `POST /auth/login`. The returned short-lived API key protects management APIs.
- `POST /predict` uses the independent `PREDICT_AUTH_KEY`, supplied as Bearer, raw `Authorization`, or `X-API-Key`.

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

Both contracts share one SQLite repository, routing core and sync queue. Set `API_COMPAT_PROFILE=master` (default) or `bupt` for root API aliases; `/compat/master/*` and `/compat/bupt/*` remain explicit. The administration UI uses the master namespace on either profile and fixed credentials `admin / telestar`; it does not use a `DEFAULT_PASSWORD` environment variable. Set `AUTH_CODE` for BUPT API access in the process environment. The LLM API key is configured in the Settings page and saved locally; other provider keys remain environment-only.

For populated installations, use the [migration and compatibility guide](docs/changes/branch-unification/README.md). Do not reuse a BUPT index without rebuilding against migrated internal IDs. Deployment is deferred by user request.
