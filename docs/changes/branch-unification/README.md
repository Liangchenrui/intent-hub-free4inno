# master 与 intentHub-BUPT 统一：需求、设计与实施计划

日期：2026-09-17（设计），2026-09-18（实施更新）。状态：**统一实现、本地验证和历史冲突解决完成；用户明确暂不部署**。

本文件是本次统一工作的唯一权威记录，承载意图、行为规格、设计取舍、实施顺序与验收依据。后续实现应更新本文件的状态和证据，不另建重复计划。

## 1. 目标、授权与边界

用户先要求比较两个分支，随后要求参照 `ai-native-dev` 先完成设计；之后明确授权推进实施等剩余阶段，并补充“先不考虑部署”。本记录保留原设计，以下实施记录说明实际完成范围。

目标是让通用 Intent Hub 与 BUPT 部署使用同一主干、同一核心实现，通过适配层和部署配置保持兼容，结束功能修复需要在两个分支重复开发的状态。

本轮交付：统一代码、迁移工具、兼容 API、一套管理界面、回归证据、文档及 Git 历史整合。真实运行数据迁移、生产服务切换和部署不在本轮执行范围。

后续统一范围：路由与兜底、存储、同步、上游对账、两侧管理能力、接口兼容、鉴权配置、前端与容器打包。继续使用 Flask、Vue 3、Qdrant；SQLite 采用标准库，不引入新数据库服务。

不包括：新路由算法、模型效果提升承诺、多租户、权限平台、队列中间件、自动蓝绿部署、CLI 功能分支合并、两套生产数据自动拼接。移除 LangChain 不是完成统一的前提。

重要区分：**统一代码不等于把两套部署的数据放进同一数据库。** 默认两套部署分别迁移自己的数据和配置；若需要集中实际业务数据，使用显式双来源导入与冲突映射，不能按数字 ID 自动覆盖。

## 2. 已核实的基线

本次会话已成功 `git fetch origin`，读取提交对象而不是未提交的运行时配置。规划时复核分支引用仍为：

| 项目 | 基线 |
| --- | --- |
| master | `1cc3bfbd3768fff8ccfb66647837137b85a8cb88` |
| intentHub-BUPT | `36df30b9a21d7e8b2454bbd1fad38463ec1397de` |
| 共同祖先 | `70fe18eb0335a099be4e69963bd0ec7d6a7dd952` |
| 分叉后独有提交 | master 13，BUPT 10 |
| 两端差异 | 136 文件；master → BUPT 为 4,827 行新增、18,347 行删除 |
| 三方合并模拟 | 64 个冲突路径，包含内容、双方新增和修改/删除冲突 |

复现命令（读取基线或在 Git 对象库生成模拟树，不 checkout、不改工作树）：

```powershell
git rev-parse origin/master origin/intentHub-BUPT
git merge-base origin/master origin/intentHub-BUPT
git rev-list --left-right --count origin/master...origin/intentHub-BUPT
git diff --stat origin/master origin/intentHub-BUPT
git merge-tree --write-tree --name-only origin/master origin/intentHub-BUPT
```

`merge-tree` 返回 1 表示存在冲突，不代表实施失败或已经进入 merge 状态。实施开始时重新核实引用；若远端推进，更新差异和契约快照后再实施。

主工作区存在用户对 `data/diagnostics_cache.json`、`data/routes.json`、`data/settings.json` 的修改，以及若干 Python 文件和 `docs/research/` 未跟踪内容；不得覆盖、暂存或清理这些内容。本地 `intentHub-BUPT` 落后远端 3 个提交，不作为来源。

| 维度 | master 当前实现 | BUPT 当前实现 |
| --- | --- | --- |
| 实体与存储 | `RouteConfig`、稳定 `route_key`、JSON `RouteManager` | `Agent`、`details`、SQLite `AgentStore` |
| 来源 | 手工、JSON 导入、上游；来源快照与人工覆盖 | local/upstream；来源快照与人工覆盖 |
| 生命周期 | active/draft/stale/disabled | active/inactive/deleted |
| 路由入口 | `/predict`，`text`，直接返回数组 | `/route`，`query`，success/data/error 外壳 |
| 路由能力 | 分组语义检索、多结果、负例、阈值、定义向量 LLM 兜底 | 同样具备上述能力 |
| 同步 | 后台队列、版本状态、任务恢复；普通 reindex 为 202 | HTTP 内等待同步；SQLite 哈希状态与删除比例保护 |
| Embedding | Qwen/TEI | TEI，返回数量不符报错 |
| 管理 | 导入、反馈、上游对账、异步诊断、国际化 | 语料推荐、上游对账、诊断、合并 Agent、精简界面 |
| 身份与打包 | 登录/API key，预测有单独鉴权逻辑 | 静态访问码，Nginx 注入访问码，密钥环境注入、排除镜像运行数据 |

不得从历史提交标题推断现状：BUPT 当前 full sync 清空并重写指定 collection，并非蓝绿切换。两侧 LLM 兜底均已存在，无须再移植两份；旧测试记录不等于统一版验证通过。

可定位的代码依据（路径相对仓库；BUPT 文件通过固定提交读取）：

- master：[`models.py`](../../../intent-hub-backend/intent_hub/models.py)、[`prediction_service.py`](../../../intent-hub-backend/intent_hub/services/prediction_service.py)、[`sync_task_service.py`](../../../intent-hub-backend/intent_hub/services/sync_task_service.py)、[`api/reindex.py`](../../../intent-hub-backend/intent_hub/api/reindex.py)、[`app.py`](../../../intent-hub-backend/intent_hub/app.py)。
- BUPT：`git show 36df30b:intent-hub-backend/intent_hub/agent_store.py`；同提交的 `models.py`、`app.py`、`services/sync_service.py`、`services/diagnostic_service.py`、`services/fallback_service.py`。
- BUPT 部署边界：`git show 36df30b:intent-hub-frontend/nginx.conf.template` 与 `docker-compose.yml`。

## 3. 需求与可观察完成条件

| 编号 | 必须满足的行为 | 验收条件 |
| --- | --- | --- |
| R1 | 单一主干与业务实现 | 两个部署配置从同一提交构建；无按分支复制的预测、仓库、同步服务 |
| R2 | 两侧调用方兼容 | 旧输入、响应结构、状态码、默认结果与鉴权分别通过固定契约测试；冲突路径按显式部署配置解析 |
| R3 | 数据不丢失 | 迁移前后逐实体核对名称、描述、语料、负例、阈值、来源快照、覆盖、状态、route_key/details；不凭总数判断 |
| R4 | 匹配语义保持 | 保留所有合格实体的降序结果、负例排除、去重；非 active 和不存在实体不被返回 |
| R5 | 兜底保持 | 仅无合格语义结果时触发；最多一个实体；非法 ID/陈旧描述/超时失败安全降级，score 为 null |
| R6 | 同步可恢复 | 写入本地数据即生成持久任务；失败不标 synced；重启可恢复；并发修改不被旧任务覆盖 |
| R7 | 管理能力收敛 | 保留 master 导入/反馈/国际化与两侧上游对账；补入 BUPT 推荐/合并能力，统一界面不维护两套页面 |
| R8 | 部署密钥与数据隔离 | 密钥仅运行时注入；API、前端、日志不回显；镜像不包含实际业务数据或凭据 |
| R9 | 可回退 | 迁移演练能用备份数据库、旧配置、旧 collection、旧代码恢复；新写入处理有明确记录 |

普通语义多结果与 LLM 歧义属于不同情形：本次不引入语义多结果仲裁，不提高或统一旧实体阈值。master 默认阈值 0.75 与 BUPT 0.8 的既有差异应在迁移与兼容创建接口中保留。

## 4. 设计决策

以下是基于当前范围选定的工程方案，不冒称用户逐条批准。实际部署拓扑和数据冲突仍须以实施时的输入核实。

### D1：从 master 演进，按能力整合

master 保有通用 route_key、导入、后台同步和管理能力，作为整合基线。BUPT 的 SQLite、运行时密钥、镜像隔离、Agent 外壳和管理补充按能力吸收。直接解决 64 个冲突很容易得到两套服务并存或静默丢功能，因此不使用“全部 ours/theirs”作为产品合并策略。

后续实现采用 `codex/unify-intent-hub` 隔离 worktree。按本文件阶段形成可回退提交，主工作区保持原样。最终目标为统一后的 master；BUPT 历史分支先保留只读，不自动删除。

如果要求 Git 历史也闭合：功能、迁移和兼容验收通过后，在隔离分支对**固定 BUPT 来源提交**执行正常双亲合并，依据已实现的能力清单解决冲突，检查合并结果相对验收树的差异并重跑受影响检查，再合入 master。不以 `merge -s ours` 或伪造祖先关系代替功能整合。远端有新增提交则先审查新增范围。该历史收敛属于后续实际合并阶段。

### D2：单一领域模型与 SQLite 权威存储

拟新增 `repository.py`/迁移模块，替换 JSON 写入路径；过渡期 `RouteManager` 和 `AgentStore` 只能作为同一仓库的适配器，不能双写两份权威数据。具体文件拆分可随实现调整。

| 统一数据 | 约束与兼容映射 |
| --- | --- |
| entity_id | 内部整数主键，向量索引使用它，不假定等于任何上游 ID |
| route_key | 全局唯一、稳定；master 保留原值，BUPT 迁移按来源与旧 ID 确定生成，禁止用易变标题生成 |
| name / description | 对应 master name/description 和 BUPT title/text |
| utterances / negative_samples / thresholds | 保留内容及当前生效阈值；规范化规则与原哈希实现核对 |
| lifecycle_status | active/draft/stale/disabled/deleted；BUPT inactive 映射 disabled，deleted 保留；只有 active 可匹配 |
| source | 来源类型、来源实例标识、来源 ID、快照、上游存在状态和人工覆盖；JSON 导入来源不丢失 |
| details | 保留 BUPT 上游原始业务详情，不作为内部主键；允许本地实体为空对象 |
| revision / synced_revision | 用于并发修改和索引状态，不以更新时间替代版本比较 |
| legacy_identity | `(contract, source_instance, legacy_id) → entity_id` 唯一映射，保存负数 ID，双来源同号不合并 |

拟使用实体、旧 ID 映射、任务、按 collection 的索引状态、schema 版本等表；多值属性可存 JSON。事务覆盖实体变更与任务入队，Qdrant 不在 SQLite 事务内。

字段覆盖恢复遵循来源快照和人工覆盖，不在上游 pull 时清除本地修改。实体合并沿用 BUPT“新建合并实体、停用两个原实体”的产品行为，但必须在本地事务内完成，并一起入队；保留来源关系以便追溯。

迁移必须保留原状态与来源信息。BUPT 兼容视图对通用 draft/stale/disabled 显示为 inactive，但内部不反向丢弃状态；普通 PATCH 未请求修改状态时不可把 draft/stale 变成 disabled。身份不明确时返回可诊断冲突，不能猜测匹配。

### D3：API 适配与同名路径冲突

共用领域服务，保留输入校验和输出序列化适配。新增固定命名空间 `/compat/master/*`、`/compat/bupt/*`，其中 `*` 为去掉原路径前导 `/` 的原接口路径。新管理台统一调用 master 兼容命名空间及显式新增管理操作。

部署配置 `API_COMPAT_PROFILE=master|bupt` 决定原有无前缀路径绑定哪套契约，默认 master；BUPT 部署显式设置 bupt。配置在启动时固定，不按 token、请求字段或响应内容猜测契约。两个固定命名空间都可注册，各自保留明确鉴权；不能用更弱的配置绕过另一套接口。

| 原接口 | 保持的契约 / 处理 |
| --- | --- |
| `/predict` | `{text}` → 数组，保留 id/name/route_key/score/match_source/fallback_status，以及原预测鉴权 |
| `/route` | `{query}` → `{success,data,error}`；data 含 matched/agents/text/match_source/fallback_status；agent 内容保留 details 语义 |
| `/routes*`、`/agents*` | 独立适配创建、编辑、删除、来源字段和旧 ID；复用仓库与任务服务 |
| `/settings`、`/diagnostics/*`、`/health/services` | 由无前缀 profile 解决契约冲突；固定命名空间可显式访问另一契约 |
| `/reindex` | 默认保持 202 任务响应；force_full 保持现有显式完成响应，不悄悄改成增量 |
| `/vectors/sync`、`/sync` | 保留 BUPT 完成后 200 的响应语义，调用统一任务执行器并等待结果，不能成功入队就谎称完成 |
| `/sync/status`、`/sync-tasks*` | 分别输出兼容聚合状态与任务状态，底层状态唯一 |

同步等待超过服务期限应明确超时，持久任务继续可查询；重试须按目标、实体版本与模式去重，不能造成并行重建。具体旧错误结构及 HTTP 状态以 P0 契约快照为准；新增超时结果需单列测试并在 API 文档标注，不伪装为原来已有行为。

保留历史默认响应，包括 master 默认路由与 BUPT 默认文本差别。本地 Agent 的 `details={}` 不在本次擅自改造成另一外壳；统一管理界面使用实体模型获取名称和 ID。

旧负数 BUPT ID 需要专项检查：现有 `<int:agent_id>` 路由可能无法匹配负数，不能把这一可达性缺陷固化为兼容要求。实现时使用支持有符号 ID 的明确路由校验，并验证编辑、删除、阈值、诊断和来源恢复。

### D4：单一路由服务与 LLM 边界

统一流程：读取当前 active 实体 → Embedding → 分组负例排除 → 分组正例匹配与当前阈值过滤 → 降序多结果 → 为空时调用唯一 FallbackService → API 映射。

语义结果不能因为向量中遗留 payload 而返回已删除或不存在的实体。兜底读取定义向量并核对模型、schema、内容哈希；分类器只接受候选 ID、no_match、ambiguous；返回前复核实体版本、collection 和模型。超时、非法返回、服务不可用均返回对应 fallback 状态，不回退成未经约束的自然语言 Agent 选择。

保留默认关闭、Top-K 和总超时配置及范围校验。不改提示词业务意图、不切换模型、不声称提高准确率。Provider 通过同一调用接口接入；首轮可以保留 master 底层调用方式，吸收 BUPT 的密钥注入和兼容行为，不为去依赖扩大重写范围。

### D5：持久同步任务与直接 collection 写入

沿用 master 队列/版本机制，吸收 BUPT 状态校验和删除比例保护。任务保存目标 collection、模型/维度、实体 revision、操作模式与重试信息，不在执行途中读取变化后的全局 collection 来决定写入目标。

建议状态：queued → running → succeeded/failed/superseded。以数据库事务领取任务，旧 worker 重启后有恢复路径。首轮部署明确单个同步 worker；不宣称仅靠进程内锁支持多 worker。读写数据库使用短事务，禁止持有写锁等待 Embedding/LLM/Qdrant 网络请求。

外部写入前尽可能完成向量生成与校验；索引失败时保留 error/pending 状态，可幂等重试。任务执行期间再次编辑实体，旧任务不得把较新 revision 标为 synced；新任务随后收敛。删除/停用实体先在权威库过滤，索引清理可以异步完成。

配置与业务编辑的影响要分开：collection/模型/维度变化触发显式迁移或重建，普通阈值修改不伪造维度兼容。超过删除比例保护或 full 重建需显式模式，不自动升级为全量。

默认继续直接写用户指定 collection，不创建 `__active` 别名，也不自动改 collection 名。首次迁移建议显式指定一个新 collection 进行验证；这属于操作者选择，不是系统自动蓝绿。直接原地 full 会有索引不完整窗口，界面应提示并展示状态。

### D6：鉴权、配置与前端

业务 profile 与鉴权配置分离：保留 master 登录/API key 和 `/predict` 专用校验；BUPT 适配入口使用环境注入的静态访问码。未配置相应凭据时拒绝访问，不能自动回落为另一凭据或匿名。

迁移不把密钥写入 SQLite、示例 JSON、前端产物或日志。无须调用的上游/LLM 服务不应阻塞进程启动；启用相应能力时校验所需凭据。配置层明确环境密钥优先，迁移遇到旧文件密钥仅输出变量名与迁移要求，不输出值；原始文件由操作者安全保留。

BUPT 现有 Nginx 自动注入访问码意味着浏览器无需自行证明身份。统一版默认不自动启用该代理行为；为原部署保留显式的受信网关配置示例，启用前核实网关已有访问控制。不能将此模式描述为逐用户鉴权，也不能默认代理注入管理端万能凭据。

管理台保留一套 Vue 页面与国际化，补入 BUPT 语料推荐/合并操作。同步采用任务轮询；健康状态独立加载，失败不能阻塞整页。loading/empty/error、重试、迁移冲突、重建状态与兜底来源均应可辨认。暂不单独设计新版视觉系统。

## 5. 数据迁移与恢复规格

1. **离线清点与 dry-run**：输入为明确的 master JSON 或 BUPT SQLite 副本；验证 schema、唯一键、状态、字段完整性和来源实例。默认只迁移一个部署来源，不主动读取当前运行目录。
2. **生成映射**：保留现有 route_key 和各契约旧 ID；BUPT 缺失 route_key 用稳定来源键生成。重复业务键、非法记录、缺失来源标识输出脱敏冲突清单，整批不写入。不得按相似标题自动去重。
3. **写入新 SQLite 文件**：在事务中写实体、映射、schema 版本、迁移输入指纹；相同输入重复执行不增记录，目标有不相容数据时拒绝覆盖。验证成功后才选择该文件作为运行库。
4. **重建或验证索引**：统一内部 ID/哈希后旧向量不能默认复用。明确 collection 和模型/维度，重建正负例及定义向量；核对每实体文本、point 类型、数量、实体 ID、哈希。metadata 点必须排除在普通路由、诊断、恢复语料之外。
5. **影子验证与切换**：对同一离线输入比较旧/新 API 输出和路由结果；冻结旧端写入后迁移最终快照并重建/校验；切换数据库与 collection 配置。不在本轮执行此动作。
6. **恢复**：保留旧代码、数据、配置与 collection；切换前失败删除或隔离本次新产物即可。切换后若已有新写入，先停写并导出增量/变更记录，不能直接回切造成新数据丢失；协调迁回或明确放弃哪些新写入后才能恢复旧服务。

从 Qdrant 恢复仅作为灾难恢复/导入工具，不替代完整数据库备份；向量 payload 不保证包含 route_key、details、来源快照等所有业务字段。不得将“恢复语料成功”标记为“业务数据完整恢复”。

## 6. 实施任务与依赖

以下为原实施分解；实际完成程度与证据见第 9 节。表内“拟新增”文件已按实现入口落地，未执行的生产演练不计作完成。

| 阶段 | 输入与修改入口 | 产物与完成条件 | 依赖 |
| --- | --- | --- | --- |
| P0 契约基线 | 两个固定提交的 app/models/auth、预测/同步/设置/诊断测试 | 在隔离 worktree 运行两侧测试与构建；留存脱敏请求/响应和错误 fixture；覆盖冲突路径与负数 ID；记录已有失败 | 无 |
| P1 数据与迁移 | master route_manager/models；BUPT agent_store/agent_compare；拟新增 repository/migrations | 单一 SQLite 仓库、兼容模型、dry-run 和幂等迁移；逐实体验证、ID 冲突拒绝、失败不污染原数据 | P0 |
| P2 最小端到端切片 | core/components、prediction/fallback、API 适配、qdrant_wrapper | 一个迁移实体从 SQLite → 隔离 Qdrant → `/predict` 与 `/route` 输出通过；含无匹配/负例/兜底失败场景 | P1 |
| P3 写入与同步收敛 | route_service、sync_service、sync_task_service、上游服务 | CRUD/导入/反馈/pull 共用仓库与任务；按 revision 同步、重启恢复、删除保护、兼容同步等待 | P2 |
| P4 管理 API 与安全 | app/api、config/auth、collection/diagnostic 服务、Dockerfile/compose/nginx | 固定命名空间和 profile；补入推荐/合并；鉴权矩阵、密钥环境注入、镜像排除验证 | P3 |
| P5 统一前端 | src/api、router、四个管理页面、i18n | 一套页面适配两个部署；任务和健康状态、来源对账、导入/反馈/合并流程浏览器验证 | P4 |
| P6 迁移演练与发布准备 | 两侧脱敏数据副本、隔离服务、API/ARCHITECTURE/USER_GUIDE/README | 全量契约回归、数据与索引对账、回退演练、单版本双配置构建；记录未验证外部项 | P5 |
| P7 历史与交付收敛 | 验收通过的整合分支与固定 BUPT 来源提交 | 实际 Git 合并及差异复核；更新 OpenAPI、部署说明与证据；按当时授权提交/推送/上线，保留旧分支 | P6 |

不预估固定工期：P0 的现有测试与契约边界、P1 的真实数据清点会影响工作量。阶段顺序不代表每一步都需要人工审批；后续授权已包含实现和合并，部署按用户决定暂缓。

## 7. 验收矩阵与证明方式

| 测试组 | 场景 | 必须观察到的结果 | 对应需求 |
| --- | --- | --- | --- |
| API 契约 | 两种路由输入、非法参数、默认结果、同名接口两种 profile | 字段/状态码/外壳对应 fixture；无自动猜测 profile | R2 |
| 实体迁移 | master/BUPT 单源、负 ID、相同数字 ID、重复 route_key、重复执行、迁移中断 | 字段逐项一致；跨来源不覆盖；重复输入幂等；失败可恢复 | R3/R9 |
| 匹配回归 | 多命中、阈值边界、负例、高分残留索引、非 active | 所有合格 active 实体排序去重；其余不返回 | R4 |
| 兜底 | 关闭/命中/no_match/ambiguous/非法 ID/超时/陈旧向量/并发修改 | 正确 source/status；最多一个；score=null；不误选 | R5 |
| 同步恢复 | 编辑后立即返回、连续编辑、重试、kill/restart、切 collection、full 失败 | 任务持久；旧 revision 不覆盖；目标固定；失败不标成功 | R6 |
| 索引验证 | 正负例与描述 metadata、新模型维度、源数据缺失 | 点数与哈希符合；metadata 不混入语料；维度不符阻止错误写入 | R3/R6 |
| 来源与管理 | pull 后人工覆盖、恢复来源字段、反馈、导入、合并实体 | 覆盖保留；显式恢复才改变；合并原实体停用且不再路由 | R7 |
| 身份与配置 | 无凭据/错误凭据/跨契约凭据/预测专用凭据/网关模式 | 明确拒绝或允许；不扩大原信任边界；不回显密钥 | R2/R8 |
| 构建与 UI | 双部署配置、loading/error/empty、长同步和兜底标签 | 同一版本构建通过；关键页面可操作；无两套业务实现 | R1/R7 |
| 恢复演练 | 切换前失败、切换后有新写入 | 可按步骤恢复；新写入可定位，不静默丢失 | R9 |

计划执行的基础检查：

```powershell
pytest intent-hub-backend/tests -q
# 在 intent-hub-frontend 目录执行
npm run build
```

以上不足以证明迁移、真实接口和 UI 正确，还须执行表内专项验证。`python -m scripts.api_docs check` 在当前仓库缺少模块，不列为已可用检查；实施时依据 Flask 路由、Pydantic 模型、契约 fixture 核对 OpenAPI，必要时补最小一致性检查。

本任务不改变模型能力目标，优先用确定性响应 fixture 验证兼容；真实 LLM/Embedding/Qdrant 联调使用明确测试服务与脱敏输入，单独记录模型、维度、输入版本和实际结果。离线 mock 不能证明真实模型准确率或生产可用性。

## 8. 开始实现前与上线前的输入边界

**无需额外输入即可开展的后续工程工作**：P0 基线、隔离实现、合成数据迁移测试、统一仓库与契约适配。当前未执行是用户限定本轮范围，并非 Skill 要求额外批准。

**真实迁移/上线前必须核实**：两套部署是否继续独立；实际数据副本和来源实例标识；调用方是否依赖无前缀冲突路径；BUPT 入口是否已有网关身份控制；目标 collection、模型维度、维护窗口和备份位置。缺少这些信息只阻塞对应真实环境动作，不阻塞本地实现。

若最终要求两个调用方访问同一个实例且都不能修改同名旧路径，则用不同域名/网关前缀分别转发固定命名空间；若部署也不能区分入口，则这是无法同时满足的契约冲突，需在上线前选择调用方迁移方案，不能用隐式请求猜测解决。

## 9. 实施结果与证据（2026-09-18 事后整理）

### 已落地的实现

- `repository.py` 统一 SQLite 实体、身份映射、任务和 outbox；事务内同时记录业务变更及待同步意图。每次变更有独立 token，旧任务不能清除较新删除事件。
- `migrate.py` 提供 master JSON/BUPT SQLite 的默认 dry-run、显式 apply、指纹幂等、键/ID 冲突预检与事务回滚。源文件只读。混合迁移先 master 后 BUPT；不自动拼接真实业务库。
- `/compat/master/*`、`/compat/bupt/*` 使用同一个核心；`API_COMPAT_PROFILE` 决定根路径的冲突接口。BUPT 有符号旧 ID 经映射访问统一内部 ID；向量恢复也使用映射，保留现有 details。
- BUPT 的推荐、合并、details/来源比较接入统一实现；管理台固定使用 master 命名空间，保留登录和国际化，新增负例建议、合并、停用标记。
- 同步任务持久化、重启恢复、目标变更 superseded、版本检查；两种同步响应适配同一执行器。删除/停用记录即时从预测过滤。
- 密钥仅从环境注入；设置接口不返回/修改密钥或启动鉴权项；无内置默认密码。两种凭据不交叉接受。Docker 上下文排除实际数据、环境文件与依赖目录。

### 本地证据

- 基线：master 84 个测试通过（[原始输出](evidence/master-baseline.txt)）；BUPT 81 个测试通过（本会话隔离 worktree 执行，未保存原始日志，不与统一版测试数混算）。
- 统一版：最终 **118 passed，5 warnings**（55.36 秒）；[后端输出](evidence/backend.txt)、[JUnit](evidence/backend.xml)；覆盖双契约、鉴权、迁移、负 ID、合并、重启、目标变化、并发 outbox 及原有回归。
- 前端：[构建输出](evidence/frontend-build.txt)，TypeScript 检查及 Vite 构建通过；保留既有大 chunk 警告。
- 浏览器：[可复现离线 fixture](evidence/ui_fixture.py)、[观察摘要](evidence/ui-check.json)。实际完成登录、推荐负例、保存、合并及刷新后停用/同步状态验证；SQLite 和内存 Qdrant 为真实组件，Embedding/LLM 为确定性替身。
- [OpenAPI 清单](../../intent-hub-openapi.json) 由 `python -m intent_hub.openapi` 生成，`--check` 核对注册路由及模型；这是接口清单和主要 DTO schema，尚非每个响应的完整形式化规格。

复现：在后端目录运行 `python -m pytest -q`（先确保 `.tmp` 目录存在）；前端运行 `npm ci`、`npm run build`；仓库根目录设置 `PYTHONPATH=intent-hub-backend` 后运行 `python -m intent_hub.openapi --check`。UI fixture 从仓库根目录运行 `python docs/changes/branch-unification/evidence/ui_fixture.py`，仅监听 `127.0.0.1:5188`，使用合成测试账号。

### 相对原设计的明确调整与限制

- P0–P5 的实现和相关本地检查已执行；P6 完成合成数据迁移/失败恢复检查及发布文档。真实生产快照、外部模型服务、生产 Qdrant、在线切换与生产恢复演练未执行。P7 的 Git 整合结果在下方记录。
- 首版只支持单进程同步 worker；SQLite 持久化不等于分布式任务领取。配置变更后旧目标任务作废，重新为当前目标排队；没有实现跨 collection 的独立并行执行。
- BUPT `full` 加局部 `agent_ids` 明确返回 400，避免错误清空未选实体；同步等待超时返回错误，任务可继续查询。BUPT 服务健康接口增加鉴权。
- 向量恢复不能补齐 payload 中不存在的业务字段，旧向量 ID/模型不保证可直接沿用，恢复记录标为待同步。真实迁移后应显式重新索引。
- UI 验证覆盖本次新增主流程，不声称所有原有页面全量端到端验收；真实 LLM 的推荐质量与路由准确率没有新增实测结论。
- 未进行 Docker 镜像构建/启动或部署；已检查打包排除规则并通过 `docker compose config --quiet` 配置解析。用户原有运行时 JSON、脚本和研究文档保留。

### Git 冲突处理记录

统一实现先保存为 `f3a2f94`，随后以普通双亲 merge 合入 `origin/intentHub-BUPT` 的 `36df30b9`。按能力核对后采用如下解决方式：

| 变化组 | 解决方式 |
| --- | --- |
| 存储、模型、路由、同步、鉴权、API 冲突 | 保留已通过 108 项回归的统一核心；BUPT 行为已接入 `compat_*`、`AgentStore` 适配层、来源比较和 LLM 推荐服务 |
| BUPT 删除的 master API、登录、国际化、导入、反馈及历史文档 | 保留；这些是统一版必须继续支持的能力 |
| Compose 自动生成重复 environment、前端万能访问码代理 | 使用统一版环境凭据与浏览器登录；不采用代理注入；入口脚本补齐 SQLite 挂载目录权限 |
| BUPT 新增默认响应、配置示例、演示文档 | 保留；历史演示明确标为历史材料；运行数据仍不打进镜像 |
| 测试 | 移植来源比较、LLM 提示词、镜像排除、TEI 编码测试；旧存储构造器/直接 provider 实现测试由统一仓库、兼容 API 和密钥隔离回归覆盖，原件可在 BUPT 历史查阅 |
| 旧向量哈希 | 采用统一 RouteConfig 内容哈希；不承诺兼容旧内部哈希，迁移要求重建索引 |
| BUPT 既有 fallback UI 证据 | 单独保存为 `evidence/bupt-prior-ui-check.json`，不混入本轮证据 |

移植编码测试时发现旧测试会在构造器探测外部 Embedding URL，并得到 404；已为构造器注入测试替身。该探测不计作外部服务验证，后续回归使用离线替身。

最终合并工作树已通过 118 项后端测试、前端 TypeScript/Vite 构建、OpenAPI 一致性和 Compose 配置解析。5 条后端警告为既有 Pydantic `dict()` 弃用提示；前端仍有既有的大 chunk 提示。没有以真实 Provider、生产数据或部署结果替代本地测试结论。
