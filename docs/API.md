# API

管理接口使用登录返回的 API key；`POST /auth/login` 免鉴权。`POST /predict` 使用独立 `PREDICT_AUTH_KEY`。

- `POST /auth/login`
- `GET /health` and authenticated `GET /health/services`
- `POST /predict`
- `GET|POST /routes`
- `GET /routes/search`
- `POST /routes/upstream-pull`
- `GET /routes/{route_id}/upstream-diff`
- `POST /routes/{route_id}/restore-upstream-fields`
- `PUT|DELETE /routes/{route_id}`
- `POST /routes/generate-utterances`
- `POST /routes/import` and `/routes/import-skill`
- `POST|DELETE /routes/{route_id}/negative-samples`
- `POST|DELETE /routes/{route_id}/feedback/positive`
- `POST|DELETE /routes/{route_id}/feedback/negative`
- `POST /reindex`（默认返回 `202` 和异步 `incremental_reindex` 任务；仅 `force_full=true` 时同步执行显式全量重建）
- `POST /reindex/sync-route`
- `GET /sync-tasks`（可使用 `active=true` 仅查询活动任务）
- `POST /sync-tasks/{task_id}/retry`
- `GET /diagnostics/overlap` and `/diagnostics/overlap/{route_id}`
- `GET /diagnostics/umap`
- `POST /diagnostics/repair` (`language`: `zh` or `en`)
- `POST /diagnostics/apply-repair`
- `GET|POST /settings`
- `GET /settings/qdrant-collections`
- `POST /settings/qdrant-collections`
- `POST /settings/qdrant-import`

路由写接口先持久化本地配置并返回，向量生成与 Qdrant 写入由后台任务完成。响应中的 `route.sync` 包含 `status`、`version`、`synced_version`、`task_id` 和失败信息。只有 `version == synced_version` 且 `status == synced` 时，向量索引才与该路由的最新配置一致。

普通手工同步请求体为 `{"force_full": false}`（也可省略字段），接口立即返回可通过 `/sync-tasks` 查询的任务。任务的 `result` 包含 `new_routes`、`updated_routes`、`deleted_routes`、`skipped_routes` 和 `total_points`。全量重建是恢复或迁移操作，不是管理台普通同步按钮的默认路径。
