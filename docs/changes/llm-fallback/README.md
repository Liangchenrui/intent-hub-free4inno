# 大模型兜底：BUPT 分支适配记录

2026-09-10，按用户要求将 master 的提交 `1cc3bfbd3768fff8ccfb66647837137b85a8cb88` 同步到 `intentHub-BUPT`。目标分支基线为 `3bfc79c`。由于接口、数据模型和模型客户端不同，采用功能适配，保留 BUPT 的 `/route` envelope、普通多结果路由、SQLite AgentStore 和环境变量凭据规则。

## 目标与设计

- 仅当原有阈值及负例过滤后没有匹配，且开关开启时，复用 query embedding 检索当前 Collection 的 Agent 名称 `title`、描述 `text`。
- 为 active Agent 增加一个标记元数据向量点；普通正负例 payload 不增加或删改字段。普通检索、诊断和语料恢复排除元数据点。
- 模型只从有效候选选择一个 Agent，允许 `no_match`、`ambiguous`；无候选、无效输出和调用失败均保留默认文本。
- 召回前保留负例排除；召回后校验内容 hash，返回前重读 Agent，防止并发编辑、删除或禁用导致过期选择。
- 配置默认关闭，Top-K 5、模型调用超时 8 秒；固定温度 0，不重试。BUPT 通过请求内的异步 HTTP 客户端直接访问现有 provider，避免引入 master 的 LangChain 依赖或跨事件循环共享连接。
- 只同步源码、测试、示例和文档。本次不访问或修改远端业务数据，不执行生产部署，不复制 master 的登录流程、密钥设置或本地路由管理实现。

## 验证与交付状态

实现、自动化验证和离线界面验证已完成；本次提交、推送结果以本分支 Git 历史为准。未执行 BUPT 环境部署或真实模型效果评估。master 的 84 项测试及真实服务演示不能作为本分支已通过的证据。

| 检查 | 本分支实际结果 | 证据与边界 |
| --- | --- | --- |
| 改动前基线 | 47 项测试通过 | `3bfc79c`，本机隔离 worktree 执行 |
| 改动后全量后端测试 | **81 passed，37.76 秒** | [控制台](evidence/backend-pytest.txt)、[JUnit](evidence/backend-pytest.xml)；其中 34 项为新增参数化兜底测试 |
| 前端类型检查与构建 | 通过，10.71 秒 | [构建记录](evidence/frontend-build.txt)；保留既有大于 500 KB chunk 提示 |
| 浏览器渲染与交互 | 模型命中展示、歧义提示、关闭开关后参数禁用通过 | [UI 观察记录](evidence/ui-check.json)；本机构建产物 + 模拟 API，无外部服务调用 |
| 运行凭据与镜像边界 | 原有安全及打包回归测试通过 | 不恢复 master 的密钥配置表单、硬编码鉴权或运行文件 |
| 真实生成／部署 | 未执行 | 不把传输 stub 或前端模拟返回当作模型准确率证据 |

全部结果于 2026-09-10 在 Windows / Python 3.13.5 的隔离 worktree 中产生。源码与示例的校验和见 [source-version.json](evidence/source-version.json)，JUnit 仅移除了机器 hostname 属性。首次适配测试为 77 passed、2 failed：测试复制 Agent 沿用了唯一 upstream_id，以及连续连接测试沿用了专测 deadline 的 1 秒配置。修正 fixture、以 5 秒验证连续连接后通过；独立 1 秒超时用例保留。随后加入设置接口和 Gemini 传输验证，全量得到上述 81 项通过结果。

## 实现与验收对应

| 行为 | 代码入口 | 验证 |
| --- | --- | --- |
| 普通多结果命中保持，关闭功能不调用模型 | [prediction_service.py](../../../intent-hub-backend/intent_hub/services/prediction_service.py) | 原多结果回归测试、`test_disabled_or_existing_match_does_not_call_model` |
| 复用查询向量、返回一个有效 Agent details | [fallback_service.py](../../../intent-hub-backend/intent_hub/services/fallback_service.py) | `test_unmatched_reuses_query_and_returns_upstream_details` |
| 拒绝、歧义、非法 ID／JSON、超时／401 | 同上 | `test_abstention_and_invalid_outputs_preserve_default`、`test_model_failure_is_bounded_without_retry` |
| 负例、停用、删除、过期和旧元数据排除 | 同上 | `test_ineligible_agents_never_reach_model`、`test_edit_during_model_call_rejects_stale_selection` |
| 描述向量补齐、复用与空语料 Agent 支持 | [sync_service.py](../../../intent-hub-backend/intent_hub/services/sync_service.py)、[intent_description.py](../../../intent-hub-backend/intent_hub/intent_description.py) | `test_sync_backfills_missing_metadata_and_reuses_unchanged_description`、`test_description_only_agent_can_be_synced_and_routed`、`test_sync_write_failure_does_not_acknowledge_changed_hash` |
| 元数据不污染例句、诊断和语料恢复 | [qdrant_wrapper.py](../../../intent-hub-backend/intent_hub/qdrant_wrapper.py)、[collection_service.py](../../../intent-hub-backend/intent_hub/services/collection_service.py) | `test_metadata_is_excluded_from_corpus_and_filters_before_top_k`、已有 Collection 恢复测试新增元数据输入 |
| BUPT 鉴权与 envelope 保持 | [app.py](../../../intent-hub-backend/intent_hub/app.py)（沿用） | `test_route_api_preserves_bupt_envelope_and_auth` |
| 设置校验先于变更，凭据仅在环境中 | [config.py](../../../intent-hub-backend/intent_hub/config.py) | `test_settings_reject_invalid_values_before_mutation`、`test_settings_api_saves_controls_without_exposing_secrets`及原安全回归 |
| 请求内客户端、Gemini 请求格式 | [fallback_service.py](../../../intent-hub-backend/intent_hub/services/fallback_service.py) | `test_consecutive_real_http_calls_use_request_scoped_clients`、`test_gemini_uses_constrained_instructions_and_private_header` |
| 空分数与兜底状态显示 | [AgentTest.vue](../../../intent-hub-frontend/src/views/AgentTest.vue)、[Settings.vue](../../../intent-hub-frontend/src/views/Settings.vue) | 类型检查、构建及浏览器模拟场景 |

新增后端测试集中在 [test_llm_fallback.py](../../../intent-hub-backend/tests/test_llm_fallback.py)。主要使用真实内存 Qdrant、临时 SQLite 和模拟 HTTP 模型响应；连续请求测试访问本地 HTTP server，证明客户端生命周期，不证明远端 provider 的分类效果。

## 与 master 的适配差异

- `RouteConfig.name/description` 对应 BUPT 的 `Agent.title/text`；读取 AgentStore，未引入 master 的 routes.json、RouteManager 或异步任务服务。
- 对外继续使用 `/route` 和 `agents[]`，新增的来源及状态在 `data` 内；不是 master 的 `/predict` 列表响应。普通命中返回所有合格 Agent，兜底至多返回一个 Agent。
- BUPT 原来没有恢复元数据点，此处只新增描述检索元数据，不把完整 Agent details 复制进 Qdrant。描述点不能作为正向语料恢复。
- 描述、模型元数据名称和描述索引版本参与 Agent hash；首次升级触发补齐。Agent hash 变化时仍按 BUPT 原策略替换该 Agent 的语料点，名称／描述未变则复用描述向量。无变化的再次同步不重新编码。
- 不引入 LangChain，新增直接依赖 `httpx>=0.27.0`。Gemini 使用 `x-goog-api-key` Header；OpenAI 兼容服务使用 Bearer。异常仅记录类型，不记录 provider 返回正文或密钥 URL。
- [OpenAPI](../../intent-hub-openapi.json) 同步新增字段，并纠正既有 `/route` 单 Agent 示例，使其与本分支已存在的多 Agent 响应一致。需求与操作契约以 [API](../../API.md)、[架构](../../ARCHITECTURE.md) 和 [用户指南](../../../USER_GUIDE.md) 为准。

## 启用、验证与回退

1. 在目标环境更新本分支代码／镜像及依赖，沿用环境注入的 `LLM_API_KEY`、`QDRANT_API_KEY`、`AGENT_API_TOKEN`、`AUTH_CODE`。不要把凭据写进 settings.json 或前端。部署方式仍按项目既有 Compose／1Panel 说明；本次未执行部署。
2. 保持开关关闭，确认当前选定 Collection 和 Agent 来源正确，调用 `POST /vectors/sync`，请求体 `{"mode":"incremental"}`，等待返回成功。升级不要求清空 Collection；旧哈希会触发描述索引补齐。通过 `/sync/status` 核对 `synced=true`，点数为 active Agent 的正例数、负例数及每个 Agent 一个描述点之和。
3. 在设置页配置有效模型和 Base URL，开启兜底，默认 Top-K 5、模型 deadline 8 秒。原有阈值保持；检索没有额外强制相似度门槛，职责边界由模型判别，允许拒绝。过期候选被过滤后可能不足 Top-K，当前不补召回。
4. 通过 `POST /route` 执行普通命中、长尾、边界拒绝、域外、歧义及负例用例。直接 API 请求带环境配置的鉴权；浏览器继续使用原 nginx 代理。核对业务字段，不仅检查 HTTP 200。模型失败应为 `unavailable`，不能计作正确 `no_match`。
5. 功能回退只需将 `LLM_FALLBACK_ENABLED` 设为 false，保留描述点；当前代码的普通语料检索会排除这些点。**若回滚到完全不识别描述点的旧版本，必须在备份并确认范围后重建旧格式索引或切换回旧 Collection**，否则旧版检索可能将描述点当正例。此项数据操作未在本次执行。

正式示例为 [llm-fallback-demo.json](../../examples/llm-fallback-demo.json)，包含六个 Agent 和六条待核对用例，从源提交示例转换为 BUPT 字段。高阈值 0.99 仅用于演示触发，不推荐用于生产。该文件用于离线测试或获准的隔离数据集，不会自动导入现有 BUPT 上游或业务 Collection。六个示例全部同步后应有 36 点，但本次未在 BUPT 远端创建此数据集。

复跑程序测试和前端构建：

```powershell
# 仓库根目录，确保导入当前 BUPT 工作区而非另一个已安装版本
$env:PYTHONPATH = (Join-Path $PWD 'intent-hub-backend')
python -m pytest intent-hub-backend/tests -q
# 在 intent-hub-frontend 中
npm ci --no-audit --no-fund
npm run build
```

后续上线仍需验证真实业务样本的正确补回、误接、拒绝、歧义、成本及延迟，模型超时不等于 `/route` 的总时延上限。本次同步只交付经过上述验证的分支代码和记录。
