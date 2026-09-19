# 运行日志与路由记录

## 2026-09-18 增量：阶段耗时与事件分类

- 目标：区分路由检索、客户端初始化、模型调用等耗时；运行日志可按 routing / sync / diagnostics / management / system 筛选。
- 契约：保留 runtime / routing 两种记录结构，新增 category；查询支持 category，与其他筛选一起在分页前执行。旧记录按已知来源推断分类并标明 category_inferred，不改写历史数据。
- 计时：路由事件新增相对请求起点的 offset_ms；timings 独立记录实际执行阶段的 offset_ms、elapsed_ms、status，失败附 error_type。使用单调时钟，不记录异常正文或新增凭据。没有执行的阶段不生成耗时，旧记录显示未采集。
- 范围：仅补可观测性，不修改路由阈值、模型选择或检索算法；总耗时仍为服务端处理时间，不包含最终日志落库和浏览器传输。
- 验收：覆盖直接命中、兜底、阶段失败、异步调用、分类筛选与分页、后台同步、旧记录兼容；前端构建并检查实际页面。

### 2026-09-19 实现与验证结果

- 已实现：14 个独立计时阶段、事件相对起点、失败耗时留存、分类查询与页面类型切换；同步任务尝试汇总含任务 ID／排队／锁等待时间。阶段明细在内存采集、请求结束时一次写入，不为每个阶段新增 SQLite 写入。
- 实现入口：[计时](../../../intent-hub-backend/intent_hub/utils/route_trace.py)、[分类上下文](../../../intent-hub-backend/intent_hub/utils/log_context.py)、[日志服务](../../../intent-hub-backend/intent_hub/services/log_service.py)、[日志页面](../../../intent-hub-frontend/src/views/Logs.vue)。后台同步上下文随任务作用域退出恢复，避免分类串到其他请求。
- 自动检查：相关后端 80 项测试通过（43.80 秒）；前端 `npm run build` 通过；生成并校验 OpenAPI 98 个路径。仅有既存 Pydantic 弃用和前端包体积告警。测试公共 fixture 将 DATA_DIR 隔离到临时目录，防止后续测试日志写入本地业务日志库。
- 浏览器实测：成功登录本地管理台；运行日志“同步”分类切换后列表均为同步类型；成功路由详情展示阶段起点、耗时、占比；失败记录展示 ResponseHandlingException；历史记录明确显示未采集阶段耗时和推断分类；检查了详情实际截图排版。
- 真实请求：重启后首次“出国访问”总计 53818.966 ms，准备 21587.175 ms，编码 2151.409 ms，负例检索 30065.348 ms 后失败；重试成功选择路由 103，总计 17530.277 ms，保存全部 14 个阶段。模型请求与响应 3056.829 ms，客户端初始化 2159.901 ms；这些是单次验证，不代表性能优化或稳定延迟基线。
- 原始脱敏证据：[真实请求计时](evidence/2026-09-19-routing-timings.json)。此处历史记录为串行阶段；当前并行检索的阶段可能重叠，余量按区间并集计算，见 [路由时延优化](../routing-latency/README.md)。
- 当前运行：已重启本地 5000 后端并验证 health；5173 页面使用新前端代码。未提交、未推送、未部署生产。远程 Qdrant 曾发生超时，本次只记录定位证据，没有改动远程服务或超时策略；原有自动物理清理待完成状态不因本次变更而改变。

## 状态与已确定需求

2026-09-18：按用户要求逐步教学推进，已完成后端查询切片、运行日志采集和路由过程记录；以下完整设计尚未全部实现，未部署。

本记录为本次变更的唯一需求与设计入口。用户在对话中明确：

- 提供运行日志和路由记录，不包含操作审计。
- 在前端查询，路由记录保存用户输入全文。
- 默认保留 30 天并自动清理。

## 建议行为与验收

| 场景 | 预期行为 | 后续验证方式 |
| --- | --- | --- |
| 正常路由 | 保存输入全文、候选及分数、最终结果、耗时和请求 ID；列表摘要，详情全文 | 接口集成检查与浏览器查询 |
| 过滤候选 | 记录实际执行的阈值判断、负例排除等原因，区分召回候选与最终匹配 | 可控候选测试 |
| 兜底 | 区分进入兜底、实际调用 LLM、默认路由以及兜底结果；分数不解释为正确概率 | 关闭、成功、无匹配、失败场景测试 |
| 异常 | 运行日志记录错误及堆栈；路由记录保留已完成阶段与失败状态，未知字段不伪造 | 故障注入与请求 ID 关联查询 |
| 查询 | 一个日志页面含运行日志和路由记录两个标签；支持分页、时间和请求 ID 筛选；运行日志支持级别及消息关键词，路由记录支持输入关键词 | 接口和页面检查 |
| 重启 | 已写入记录在服务重启后仍可查询 | 临时数据目录重启检查 |
| 保留期 | 以记录创建时间计算 30 天；查询排除过期记录，后台自动分批删除 | 固定时钟边界测试 |
| 访问 | 查询接口复用现有管理鉴权，不采集认证头、API Key 或完整配置；用户输入字段依用户要求保留全文 | 鉴权、日志字段检查 |

## 建议设计与取舍

- 复用 Python logging 和现有 logger，增加持久化处理；运行日志第一版覆盖应用日志、请求完成事件和应用异常，不承诺采集全部第三方或进程启动前输出。
- 在配置的数据目录内使用独立 SQLite 日志库，便于筛选、分页、关联和到期删除；与业务库隔离。当前项目已有 SQLite 使用方式，Compose 已挂载后端 data 目录。
- 运行日志与路由记录分表，用服务端生成的请求 ID 关联；后台任务允许没有请求 ID。不改变现有路由响应正文契约。
- 从路由执行过程采集结构化证据，不解析运行日志反推候选。覆盖 `/predict`、`/route` 及对应兼容入口，每次请求只生成一条路由记录。
- 内部统一使用 UTC 时间，前端转换显示。建议启动时清理一次，运行期间每小时分批清理；停机时不执行，恢复后补清理。清理逻辑需考虑多进程并发和数据库锁。
- 查询默认隐藏过期数据；物理删除通常在过期后一个清理周期内完成。删除行不等于 SQLite 文件立即缩小。
- 日志写入失败不能把原本成功的路由请求改为失败；通过原有控制台输出可识别告警，避免日志处理器递归记录自身失败。不能承诺数据库不可写时仍完整保留记录。
- 全文内容按普通文本渲染，不作为 HTML 执行；日志查询本身不生成路由记录。

## 当前实现入口

- [现有 logger](../../../intent-hub-backend/intent_hub/utils/logger.py)
- [Flask 应用及兼容注册](../../../intent-hub-backend/intent_hub/app.py)
- [主预测服务](../../../intent-hub-backend/intent_hub/services/prediction_service.py)
- [兜底服务](../../../intent-hub-backend/intent_hub/services/fallback_service.py)
- [BUPT 接口](../../../intent-hub-backend/intent_hub/compat_api.py)及[兼容服务](../../../intent-hub-backend/intent_hub/compat_services.py)
- [前端路由](../../../intent-hub-frontend/src/router/index.ts)

## 后续教学顺序

1. 讲解并讨论上述设计，明确第一版技术边界。
2. 实现一个端到端切片：一次请求产生持久记录，并能通过鉴权接口查询。
3. 补齐两条路由链路的候选、过滤、兜底证据和异常日志。
4. 实现前端列表、筛选、详情和关联查询。
5. 验证过期清理、重启持久化、鉴权、故障降级及现有路由兼容性，补充实际证据。

## 已执行检查与限制

需求整理阶段仅检查代码及文档；用户随后要求继续，完成首个后端切片：

- [log_service.py](../../../intent-hub-backend/intent_hub/services/log_service.py)：请求 ID、请求完成记录、SQLite 存储和分页查询。
- `/predict`、`/route` 及兼容入口通过请求上下文标记已鉴权和验证的输入，保存输入全文与成功响应快照；失败时记录状态，结果为 null。两个记录类型暂存在同一 records 表，通过 kind 区分；完整设计中的分表尚未实施。
- 所有响应增加 `X-Request-ID`，原响应正文保持不变；不保存认证头。非法或未鉴权请求只有运行记录。
- `GET /logs/runtime` 与 `GET /logs/routing` 支持 `request_id`、`page`（默认 1）、`page_size`（默认 20，最大 100）。返回 items、total、page、page_size；created_at 为 UTC Unix 秒。
- 管理查询按 API_COMPAT_PROFILE 复用对应鉴权；master 模式遵循 AUTH_ENABLED，关闭认证时查询也公开。BUPT 模式使用 AUTH_CODE。查询失败返回 503，写入失败告警但不影响原响应。
- 数据存储于配置 DATA_DIR 下的 logs.sqlite3。查询隐藏超过 30 天记录；**物理自动清理尚未实现**。

验证环境：Windows PowerShell，本地 Python，2026-09-18。在后端目录使用隔离数据目录执行：

```powershell
$env:INTENT_HUB_DATA_DIR = Join-Path $PWD '.tmp/log-slice-data'
python -m pytest tests/test_request_logs.py tests/test_predict_api.py -q
```

结果：8 passed，2 条已有鉴权代码的 Pydantic dict() 弃用警告。用例位于 [test_request_logs.py](../../../intent-hub-backend/tests/test_request_logs.py)，验证全文与响应快照、鉴权、两条 BUPT 路径单次记录、数据库重新打开、分页、30 天查询边界、路由失败和数据库不可写降级。路由服务使用替身；重新打开数据库不等于真实进程重启验证。

剩余：自动清理、真实模型服务、正式运行环境的进程重启和负载验证。当前实现请求记录和每条应用日志同步写 SQLite，锁等待上限配置为 0.2 秒，尚未做负载验证。

### 第二个切片：运行日志和路由证据

用户再次要求继续后实现：

- 通过 [route_trace.py](../../../intent-hub-backend/intent_hub/utils/route_trace.py) 在 Flask 请求上下文收集 events；非 HTTP 调用不生成路由事件。事件按执行顺序保存，失败时保留已执行部分。
- 记录准备、编码、负例检索、正例检索阶段；记录实际召回的样本级候选分数、阈值和过滤结果（低于阈值、负例排除、路由缺失或不活跃）。threshold_passed 仅代表通过阈值；去重后的路由 ID 由 vector_result 给出，不能把样本条数当路由数。
- 记录 fallback_entered、定义候选是否有效或索引过期、llm_call_started、模型结构化决策及最终 fallback_result。llm_call_started 表示开始调用客户端，不证明远端收到或完成请求；未进入兜底时没有兜底事件。普通向量分数不是模型置信度。
- 现有应用 logger 和 Flask 应用 logger 在安装后增加持久化处理器，保存级别、logger 名称、消息及异常堆栈。后台日志 request_id 为空字符串；不采集所有第三方 logger，默认 INFO 等级不含 DEBUG。
- 运行消息及堆栈对 Config.SECRET_KEYS 中已配置的字符串/列表值和当前请求认证头值进行替换；不承诺识别任意未知密钥。输入全文字段仍按用户要求保存原文。LLM 服务异常正文继续沿用现有策略不采集，仅记录异常类型。
- 存储失败通过标准错误输出简短告警，不递归使用应用 logger。

验证命令（后端目录，使用隔离数据目录）：

```powershell
$env:INTENT_HUB_DATA_DIR = Join-Path $PWD '.tmp/log-trace-data'
python -m pytest tests/test_request_logs.py tests/test_predict_api.py tests/test_prediction_service.py tests/test_llm_fallback.py -q
```

结果：52 passed，3 条已有 Pydantic 弃用警告。覆盖向量预测回归、兜底开关、模拟 LLM 成功/拒绝/失败、候选过滤原因、请求事件隔离、异常堆栈持久化、运行消息脱敏和处理器失败不递归。使用本地内存 Qdrant 与模拟模型，未调用真实供应商。

随后补充失败请求保留 events 的断言，单独执行 `python -m pytest tests/test_request_logs.py::test_failed_route_record -q`，结果 1 passed。

未提交或部署；未修改用户已有的 `intent-hub-backend/data/settings.json`。

### 第三个切片：前端查询和筛选

- 新增 [Logs.vue](../../../intent-hub-frontend/src/views/Logs.vue)，主导航均可进入；分运行日志、路由记录标签，提供时间范围、请求 ID、关键词、日志级别、分页、详情和跨类型关联。支持中英文、加载中、空结果和错误提示；并发查询只接受最后一次请求结果。
- 输入全文、异常堆栈和结构化过程以纯文本展示。候选事件逐项显示，路由列表展示结果与兜底状态；缺少事件时显示未记录，不推断调用情况。
- SQLite 查询增加参数化的时间、级别和字面关键词过滤；验证非有限时间、倒序区间等非法条件。前端固定 `/compat/master/logs/*` 使用 master 管理鉴权，即使根路径处于 BUPT 模式也不会误用 AUTH_CODE。
- 更新 [API 文档](../../API.md)、[用户指南](../../../USER_GUIDE.md) 和生成的 OpenAPI 清单。

验证（2026-09-18）：

1. 后端隔离数据目录执行 `python -m pytest tests/test_request_logs.py tests/test_predict_api.py -q`：10 passed，3 条现有 Pydantic 弃用警告；新增组合过滤、字面特殊字符、非法参数和固定命名空间鉴权测试。
2. 前端 `npm run build` 通过类型检查和构建；已有主包体积告警，日志页独立分包。
3. 后端 `python -m intent_hub.openapi --check --output ../docs/intent-hub-openapi.json` 通过，清单 98 条路径。
4. 浏览器连接隔离 Vite 5187 / Flask 5087，使用测试登录和预置 25 条路由记录：验证从主导航进入、请求 ID 筛选、ERROR 级别筛选、错误堆栈详情、关联查询、原文换行及 script 标签按文本展示、候选过程、25 条分页后第二页 5 条、不匹配关键词空状态、中英文切换。停止测试后端后，页面显示明确错误并清空旧结果。

浏览器验收使用真实前后端查询链路，但路由数据预置、鉴权为隔离测试替身，不代表真实模型或生产登录验收。日期筛选已做接口边界测试，未逐项操作日期选择器；未进行移动端专项验收。测试服务仅用于本次检查，正式部署未执行。
