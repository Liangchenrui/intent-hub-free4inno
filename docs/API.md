# API

Except `GET /health` and `POST /auth/login`, send `Authorization: Bearer <api_key>`.

- `POST /auth/login` — body: `{"username":"admin","password":"..."}`.
- `GET /agents` — return all local SQLite Agents, including inactive records and a lightweight upstream comparison summary.
- `GET /agents/<id>/diff` — return field-level local/latest-upstream differences; corpus fields contain added, removed, and unchanged counts.
- `POST /agents/pull` — fetch upstream Agents into SQLite without writing vectors. The result distinguishes created, upstream-changed, unchanged, preserved overrides, and upstream-missing records.
- `POST /agents`, `PATCH /agents/<id>`, `DELETE /agents/<id>` — create, edit, or soft-delete local Agent data.
- `POST /agents/<id>/restore-fields` — restore selected manually overridden fields from the latest upstream snapshot.
- `POST /agents/<id>/recommendations` — generate positive or negative corpus suggestions without saving them.
- `POST /vectors/sync` — synchronize active local Agents to Qdrant. Send `{"mode":"full"}` for a validated blue-green rebuild.
- `POST /sync` — deprecated compatibility alias for `POST /vectors/sync`; it no longer pulls upstream data.
- `GET /sync/status` — return local pull time, pending changes, vector sync time, and point counts.
- `POST /route` — body: `{"query":"用户问题"}`. Always returns `success`, `data`, and `error`. `data` contains fixed `matched`, `agent`, `score`, and `text` fields.
- `GET /settings`, `POST /settings` — read or update Qdrant, Embedding, LLM, prompt, and diagnostic settings.
- `/diagnostics/overlap`, `/diagnostics/umap`, `/diagnostics/repair`, `/diagnostics/apply-repair`, `/diagnostics/merge` — semantic diagnosis and local repair workflow.
- `GET /health` — health check.
