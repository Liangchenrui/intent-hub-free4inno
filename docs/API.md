# API

管理接口使用登录返回的 API key；`POST /auth/login` 免鉴权。`POST /predict` 使用独立 `PREDICT_AUTH_KEY`。

- `POST /auth/login`
- `POST /predict`
- `GET|POST /routes`
- `GET /routes/search`
- `PUT|DELETE /routes/{route_id}`
- `POST /routes/generate-utterances`
- `POST /routes/import` and `/routes/import-skill`
- `POST|DELETE /routes/{route_id}/negative-samples`
- `POST|DELETE /routes/{route_id}/feedback/positive`
- `POST|DELETE /routes/{route_id}/feedback/negative`
- `POST /reindex` and `/reindex/sync-route`
- `GET /sync-tasks`（可使用 `active=true` 仅查询活动任务）
- `POST /sync-tasks/{task_id}/retry`
- `GET /diagnostics/overlap` and `/diagnostics/overlap/{route_id}`
- `GET /diagnostics/umap`
- `POST /diagnostics/repair` (`language`: `zh` or `en`)
- `POST /diagnostics/apply-repair`
- `GET|POST /settings`
- `GET /settings/qdrant-collections`
- `POST /settings/qdrant-import`

路由写接口先持久化本地配置并返回，向量生成与 Qdrant 写入由后台任务完成。响应中的 `route.sync` 包含 `status`、`version`、`synced_version`、`task_id` 和失败信息。只有 `version == synced_version` 且 `status == synced` 时，向量索引才与该路由的最新配置一致。
