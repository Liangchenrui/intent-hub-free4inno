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

## 未命中时的大模型兜底

`POST /predict` 请求体与列表响应保持兼容。现有例句匹配有结果时直接返回；结果为空（包括负例排除后为空）且开启兜底时，从当前 Collection 的名称与描述向量召回 Top-K 个意图，再调用现有 LLM 配置进行选择或拒绝。

新增响应字段：

| 字段 | 含义 |
| --- | --- |
| `match_source` | `semantic`：例句匹配；`llm_fallback`：模型选择；`default`：默认兜底 |
| `fallback_status` | 未调用兜底为 `null`；其余为 `matched`、`no_match`、`ambiguous`、`no_candidates` 或 `unavailable` |
| `score` | 保持原有例句相似度口径；模型选择与默认兜底均为 `null`，不返回模型自评置信度 |

模型只能选择候选中的一个 ID。歧义、均不适用、缺少已同步候选、超时或无效输出均返回原有默认路由，通过 `fallback_status` 区分原因；`ambiguous` 供调用方提示用户澄清，不会自动发起多轮对话。被负例排除、非 active、已删除及内容 hash 过期的实体不能进入兜底结果。基础 Embedding/例句检索故障仍按现有接口错误机制处理；这里的降级只覆盖新增兜底阶段。

`GET|POST /settings` 新增以下配置，旧设置文件缺省时无需迁移：

| 配置 | 默认值 | 范围 |
| --- | --- | --- |
| `LLM_FALLBACK_ENABLED` | `false` | 布尔值 |
| `LLM_FALLBACK_TOP_K` | `5` | 整数 1–20 |
| `LLM_FALLBACK_TIMEOUT_SECONDS` | `8` | 数值 1–60 秒，仅限制模型调用，不含前置检索 |

参数错误返回 400，校验失败不写入设置。兜底固定温度 0、关闭 SDK 重试，复用现有 provider、model、base URL 和 API key。启用前先执行一次增量同步并等待成功，旧恢复元数据中的零向量会被补齐；升级不需要清空 Collection。
