# API

管理接口使用登录返回的 API key；`POST /auth/login` 免鉴权。`POST /predict` 使用独立 `PREDICT_AUTH_KEY`。

对外路由接口的 BUPT 契约（`POST /compat/bupt/route`、`POST /route`）见 [bupt-routing-api.openapi.yaml](bupt-routing-api.openapi.yaml)；master 契约（`POST /predict`）见下文。

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


## master / BUPT 兼容入口

所有 master 路径也可使用 `/compat/master` 前缀；BUPT 使用 `/compat/bupt` 前缀。`API_COMPAT_PROFILE=master|bupt` 仅决定无前缀别名，同名 `/settings` 与 `/diagnostics/*` 不按请求参数猜测版本。管理台固定调用 master 命名空间。

- `POST /compat/bupt/route`：输入 `{"query":"查询文本"}`，返回 `{"success":true,"data":{"matched":true,"agents":[{"agent":{},"score":0.9}],"text":null,"match_source":"semantic","fallback_status":null},"error":null}`。`agent` 为原始 details；兜底命中的 score 为 null，未命中时 agents 为空数组、text 为默认文本。
- BUPT 访问使用环境 `AUTH_CODE`，支持 Bearer 或 X-API-Key；不会接受 master 的预测专用密钥替代它。master 管理登录使用本地固定凭据：`admin / 123456`。
- BUPT `/agents`、签名整数 ID 的 CRUD/diff/restore-fields/recommendations/thresholds、`/agents/pull`、`/collections*`、`/diagnostics/*` 保留适配入口。不同来源 ID 使用持久映射，不直接作为向量主键。
- BUPT `POST /vectors/sync` 与 `/sync` 使用 `mode=incremental|full`，等待共享任务完成返回 200。full 不允许同时指定局部 agent_ids，防止误删其余索引。任务失败或等待超时不会返回成功；可通过 master `/sync-tasks` 查看状态。该安全限制是明确的兼容修正。
- `POST /compat/master/routes/{route_id}/recommendations`：`{"polarity":"positive|negative","count":5}`，返回 items，仅生成建议。
- `POST /compat/master/routes/merge`：`{"source_agent_id":1,"target_agent_id":2,"title":"合并名称","text":"描述"}`，返回新 RouteConfig，HTTP 201；原实体停用，三个实体一起进入同步队列。

凭据以及 AUTH_ENABLED、数据路径等启动配置不能经设置 API 修改，提交返回 400；GET 设置不返回密钥。BUPT 服务健康接口现在同样要求鉴权，这是避免未授权暴露基础设施信息的显式安全变更。

`python -m intent_hub.openapi --check` 核对已注册的 HTTP 路径及模型清单（运行前将后端目录加入 PYTHONPATH）。生成文件为 [OpenAPI](intent-hub-openapi.json)。它不是完整错误响应证明，具体成功/失败行为由后端契约测试覆盖。

## 日志查询（开发中）

管理台入口为 `/logs`，HTTP 查询使用 `GET /compat/master/logs/runtime` 和 `GET /compat/master/logs/routing`。固定 master 命名空间复用管理台会话鉴权；无前缀 `/logs/{kind}` 按 API_COMPAT_PROFILE 使用 master 管理鉴权或 BUPT AUTH_CODE。master 的 AUTH_ENABLED=false 会关闭该鉴权。

查询参数：

| 参数 | 语义 |
| --- | --- |
| page / page_size | 页码从 1 开始；每页默认 20，最多 100 |
| request_id | 精确匹配请求 ID |
| keyword | 区分大小写的字面子串；runtime 搜索消息，routing 搜索输入全文 |
| category | routing（路由）、sync（同步）、diagnostics（诊断）、management（管理）、system（系统）；与其他过滤条件组合，分页前筛选 |
| level | 仅 runtime：DEBUG、INFO、WARNING、ERROR、CRITICAL |
| start / end | UTC Unix 秒，包含边界；开始不得晚于结束，不接受 NaN/Infinity |

返回 `{items, total, page, page_size}`。每条记录包含 id、created_at（UTC Unix 秒）、request_id；运行日志含 message、level 及可选 exception/module，路由记录含 input_text、status、result、events。请求完成事件另含 method、path、status_code、elapsed_ms。后台日志 request_id 为空字符串。新增 category 与 category_inferred；后者为 true 表示旧记录按现有信息推断分类，无法识别时归系统。同步任务完成／重试日志含 task_id、task_status、attempt、elapsed_ms、queue_wait_ms、lock_wait_ms。

路由事件 events 新增 offset_ms（相对请求起点）；timings 保存独立阶段的 stage、offset_ms、elapsed_ms、status，失败附 error_type。包括准备、编码、正负例检索与过滤、职责检索、兜底候选、提示词、LLM 客户端初始化、LLM 请求与响应、响应解析及路由复核。仅记录实际执行阶段；失败也保留耗时。旧记录没有 timings 时不能反推阶段时间。总耗时为服务端处理时间，不含最终日志落库与网络传输；timings 未覆盖的零散工作显示为其他处理，兜底汇总不与阶段重复相加。

响应状态：400 参数无效，401 鉴权失败，404 未知日志类别，503 存储不可用。当前查询隐藏超过 30 天的记录；物理自动清理尚未实现。详情与验证边界见 [变更记录](changes/logging/README.md)。


## 路由就绪与计时

`GET /health` 仅表示进程存活；`GET /health/ready`（以及 `/compat/master/health/ready`）
免鉴权，返回 `status`（pending/warming/ready/failed）、`error_type`、`elapsed_ms`。
只有 ready 返回 200，其余返回 503；就绪检查可触发后台预热，失败后 5 秒允许重试。
启动和组件配置变更后后台预热，管理接口不等待远程初始化；预热期间预测快速返回 503。
BUPT 路由仍使用统一信封，错误码为 `SERVICE_NOT_READY`。

路由 timings 可重叠：正负例并行，各阶段占比不能相加；未计时余量按区间并集计算。
`remote_call` 事件的 `elapsed_ms` 为客户端调用耗时，`server_ms` 为服务端提供的处理时间
（仅存在时提供，Qdrant REST time 秒转毫秒）；两者差值包含传输、排队和序列化等，不能直接
归因为网络。`embedding_cache.hit` 和 `llm_client.reused` 标记复用情况。
详见 [路由时延优化](changes/routing-latency/README.md)。

`SERVICE_HTTP_TRUST_ENV`（默认 true）控制 Embedding/Qdrant 是否继承环境代理和证书配置。
设置页提供开关，`POST /compat/master/settings` 可保存布尔值；字符串不被接受。
关闭后直连且仍验证 HTTPS，配置变更触发组件后台预热；LLM 不受此开关影响。


### 上游拉取任务

`POST /routes/upstream-pull`（含 `/compat/master` 前缀）返回 **202** 和 `upstream_pull` 任务，不再等待网络拉取完成。同来源配置的 queued/running 请求返回同一任务。用 `GET /sync-tasks` 查看 `phase=fetching|comparing|saved`、状态与结果。

结果含 `created`、`effective_updated`、`baseline_updated`、`unchanged`、`upstream_missing`、`failed`、`failed_source_ids`、`timings_ms`、`upstream_requests`、`detail_requests`。`updated` 保留为上游托管字段变化数量，`preserved_overrides` 为保留的覆盖字段数量。若有 `sync_task_id`，拉取成功只代表本地保存完成，须继续查看该索引任务；部分详情失败以 failed/warning 表达，重拉只保存变化项。

来源拉取任务的失败可用既有 retry 接口重试；来源配置已经变更时应新建拉取任务。BUPT `/agents/pull` 保持同步返回结果。完整设计与限制见 [上游同步记录](changes/upstream-pull/README.md)。


路由标识身份修正：上游优先使用 `route_key` / `routeKey`；当前上游未提供此字段时沿用规范化 title 生成标识。不同标识视为不同实体，来源 ID 仅用于追踪。一次拉取出现重复标识时整批报错，不按顺序覆盖。已有历史后缀标识与 `demo.1` 等自定义标识不会自动改名或合并。
