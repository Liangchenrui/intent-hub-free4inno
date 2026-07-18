# API

Except `GET /health` and `POST /auth/login`, send `Authorization: Bearer <api_key>`.

- `POST /auth/login` — body: `{"username":"admin","password":"..."}`.
- `GET /agents` — return the latest synchronized Agent snapshot.
- `POST /sync` — fetch every upstream Agent detail and rebuild the configured collection.
- `POST /route` — body: `{"query":"用户问题"}`. Always returns `success`, `data`, and `error`. `data` contains fixed `matched`, `agent`, `score`, and `text` fields.
- `GET /settings` — return the collection name.
- `POST /settings` — body: `{"QDRANT_COLLECTION":"collection"}`.
- `GET /health` — health check.
