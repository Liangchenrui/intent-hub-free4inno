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

Runtime data is stored directly in `intent-hub-backend/data/`: `routes.json`, `settings.json`, and `diagnostics_cache.json`.

```bash
pytest intent-hub-backend/tests -q
cd intent-hub-frontend && npm install && npm run build
```
