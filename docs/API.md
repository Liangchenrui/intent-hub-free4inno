# API

Except `GET /health`, send `Authorization: Bearer <runtime-auth-code>` (or `X-API-Key: <runtime-auth-code>`). The value must come from protected runtime configuration and must not be embedded in browser code or committed files.

- `GET /agents` — return all local SQLite Agents, including inactive records and a lightweight upstream comparison summary.
- `GET /agents/<id>/diff` — return field-level local/latest-upstream differences; corpus fields contain added, removed, and unchanged counts.
- `POST /agents/pull` — fetch upstream Agents into SQLite without writing vectors. The result distinguishes created, upstream-changed, unchanged, preserved overrides, and upstream-missing records.
- `POST /agents`, `PATCH /agents/<id>`, `DELETE /agents/<id>` — create, edit, or soft-delete local Agent data.
- `POST /agents/<id>/restore-fields` — restore selected manually overridden fields from the latest upstream snapshot.
- `POST /agents/<id>/recommendations` — generate positive or negative corpus suggestions without saving them.
- `POST /vectors/sync` — synchronize active local Agents to Qdrant. Send `{"mode":"full"}` to clear and rebuild the configured collection.
- `POST /sync` — deprecated compatibility alias for `POST /vectors/sync`; it no longer pulls upstream data.
- `GET /sync/status` — return local pull time, pending changes, vector sync time, and point counts.
- `POST /route` — body: `{"query":"用户问题"}`. Always returns `success`, `data`, and `error`. `data.agents` contains every Agent that reaches its threshold as `{agent, score}` entries, ordered by descending score; it is empty when no Agent matches.
- `GET /settings`, `POST /settings` — read or update non-secret Qdrant, Embedding, LLM, prompt, and diagnostic settings. Secret fields are neither returned nor accepted; configure them only through the runtime environment.
- `/diagnostics/overlap`, `/diagnostics/umap`, `/diagnostics/repair`, `/diagnostics/apply-repair`, `/diagnostics/merge` — semantic diagnosis and local repair workflow.
- `GET /health` — health check.

## 未命中时的大模型兜底

`POST /route` 继续接受 `{"query":"用户问题"}`，保留 `success/data/error` envelope。原有匹配仍返回按相似度降序排列的全部 Agent；没有合格匹配且开启兜底时，从当前 Collection 的名称、描述向量召回 Top-K，由模型选择一个有效 Agent，或拒绝／报告歧义。

`data` 增加 `match_source`（`semantic` / `llm_fallback` / `default`）和 `fallback_status`（`null` / `matched` / `no_match` / `ambiguous` / `no_candidates` / `unavailable`）。模型命中时 `agents` 有一项，其 `agent` 仍为当前 Agent details，`score=null`；拒绝或不可用时 `agents=[]`、`matched=false`，保留 `default_route.txt` 文本。模型异常不会伪装成成功拒绝。原有 Embedding／例句检索错误仍走 500 envelope。

`GET/POST /settings` 新增：`LLM_FALLBACK_ENABLED` 默认 false；`LLM_FALLBACK_TOP_K` 默认 5、整数 1–20；`LLM_FALLBACK_TIMEOUT_SECONDS` 默认 8、数值 1–60 秒。无效值返回 400 且不写文件或内存。模型调用固定温度 0、无重试；超时不包含前置检索。`LLM_API_KEY` 仍仅由环境注入，接口不接受或返回凭据。

升级后先运行 `POST /vectors/sync` 的 incremental 模式，补齐每个 active Agent 的描述向量；无需清空 Collection。`GET /sync/status` 的点数包含新增描述点。分支适配与验证证据见 [交付记录](changes/llm-fallback/README.md)。
