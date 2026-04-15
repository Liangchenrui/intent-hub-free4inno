# Intent Hub 多租户 Access Code 与 Skills 导入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前单实例 Intent Hub 改造为支持多租户、`access_code` 统一鉴权、按租户隔离 Qdrant collection 与工作区、并支持 `SKILL.md -> LLM -> JSON -> 导入` 流水线的控制面与运行时。

**Architecture:** 以后端 Flask 服务为基础，先抽出平台级与租户级上下文，再让认证、路由、设置、诊断、skills 导入全部在 `TenantContext` 下运行。保留现有 `RouteManager` / `PredictionService` / `Qdrant` 业务能力，但去掉“全局唯一配置 + 全局单例组件”的假设，并为前端补齐平台管理员视图、租户登录态和 skill JSON 草稿流。

**Tech Stack:** Flask, Pydantic, Qdrant, LangChain, Vue 3, TypeScript, Axios, pytest

---

## 0. 输入与范围

- 设计基线：
  - `intent-hub-backend/docs/2026-04-14-multi-tenant-access-code-and-skills-design.md`
- 当前后端形态：
  - 全局 `Config`
  - 全局 `ComponentManager`
  - 单份 `data/routes.json`
  - 单份 `data/settings.json`
  - 单份 `data/diagnostics_cache.json`
- 当前前端形态：
  - 单一登录页
  - 单租户路由管理、诊断、设置
  - `src/api/index.ts` 使用单一 `api_key` / `predict_auth_key`
- 本计划只覆盖设计落地，不包含真正的 `dispatch executor` 体系。

## 1. 交付拆分

建议拆成 7 个可独立验收的里程碑，每个里程碑结束都应保持主干可运行：

1. 平台与租户数据模型落地
2. 租户上下文与组件隔离
3. `access_code` 统一鉴权与新运行时接口
4. 路由来源与 JSON 导入统一化
5. skill 扫描与 JSON 草稿流水线
6. Web 控制台多租户化
7. SDK / CLI MVP

## 2. 文件责任规划

### 2.1 后端新增文件

- `intent-hub-backend/intent_hub/platform/registry.py`
  - 平台级租户注册表，负责 `tenants.json` 读写、`access_code` 查找、租户状态管理。
- `intent-hub-backend/intent_hub/platform/models.py`
  - 平台与租户元数据模型，如 `TenantRecord`、`AccessCodeRecord`、`SkillSourceRecord`。
- `intent-hub-backend/intent_hub/platform/workspace.py`
  - 按租户解析 workspace 路径与文件路径。
- `intent-hub-backend/intent_hub/tenant/context.py`
  - `TenantContext` 定义。
- `intent-hub-backend/intent_hub/tenant/components.py`
  - `TenantComponentManager` 与 `TenantComponentRegistry`。
- `intent-hub-backend/intent_hub/api/admin.py`
  - 平台管理员接口。
- `intent-hub-backend/intent_hub/api/tenant.py`
  - 租户级接口聚合。
- `intent-hub-backend/intent_hub/services/tenant_auth_service.py`
  - `access_code` 校验、hash、session/JWT 签发。
- `intent-hub-backend/intent_hub/services/import_service.py`
  - 标准 JSON 导入入口，统一 `web_manual` / `json_import`。
- `intent-hub-backend/intent_hub/services/skill_scan_service.py`
  - skill 目录扫描、hash 计算、索引维护。
- `intent-hub-backend/intent_hub/services/skill_json_generation_service.py`
  - `SKILL.md -> LLM -> 标准 route JSON draft`。
- `intent-hub-backend/intent_hub/services/runtime_route_service.py`
  - `/v1/route` 响应封装。
- `intent-hub-backend/tests/test_tenant_registry.py`
- `intent-hub-backend/tests/test_tenant_auth.py`
- `intent-hub-backend/tests/test_tenant_components.py`
- `intent-hub-backend/tests/test_import_service.py`
- `intent-hub-backend/tests/test_skill_scan_service.py`
- `intent-hub-backend/tests/test_runtime_route_api.py`

### 2.2 后端重点修改文件

- `intent-hub-backend/intent_hub/config.py`
  - 从“全局业务配置”收敛为“平台默认配置 + 路径常量 + 默认 prompt”。
- `intent-hub-backend/intent_hub/core/components.py`
  - 从全局单例组件迁移为兼容层或删除。
- `intent-hub-backend/intent_hub/auth.py`
  - 引入平台管理员鉴权与租户 `access_code` 鉴权分流。
- `intent-hub-backend/intent_hub/models.py`
  - 扩展 route source / sync / draft / tenant response 模型。
- `intent-hub-backend/intent_hub/app.py`
  - 注册 `/admin/*`、`/tenant/*`、`/v1/*`。
- `intent-hub-backend/intent_hub/services/prediction_service.py`
  - 改为接受 `TenantContext` 或租户组件。
- `intent-hub-backend/intent_hub/services/route_service.py`
  - 去掉 skill 直接导入正式路由的表达，统一走 JSON draft / import。
- `intent-hub-backend/intent_hub/services/diagnostic_service.py`
  - 缓存路径改为租户级。
- `intent-hub-backend/intent_hub/services/sync_service.py`
  - 基于租户 collection 重建。

### 2.3 前端重点修改文件

- `intent-hub-frontend/src/api/index.ts`
  - 区分平台管理员 token、租户 session、运行时 code。
- `intent-hub-frontend/src/router/index.ts`
  - 区分 `/admin/*` 与 `/tenant/*` 路由守卫。
- `intent-hub-frontend/src/views/Login.vue`
  - 支持管理员登录与 `access_code` 登录。
- `intent-hub-frontend/src/views/AgentList.vue`
  - 迁移为租户路由列表页。
- `intent-hub-frontend/src/views/Settings.vue`
  - 改为租户设置页。
- `intent-hub-frontend/src/views/Diagnostics.vue`
  - 改为租户诊断页。
- 新增：
  - `intent-hub-frontend/src/views/admin/TenantList.vue`
  - `intent-hub-frontend/src/views/admin/TenantDetail.vue`
  - `intent-hub-frontend/src/views/tenant/SkillSources.vue`
  - `intent-hub-frontend/src/views/tenant/SkillDrafts.vue`

### 2.4 文档与样例文件

- `intent-hub-backend/docs/API.md`
- `intent-hub-backend/docs/STRUCTURE.md`
- `intent-hub-backend/data/platform/admin_settings.json.example`
- `intent-hub-backend/data/platform/tenants.json.example`
- `intent-hub-backend/data/tenants/default/settings.json.example`
- `intent-hub-backend/data/tenants/default/routes.json.example`

## 3. 里程碑 1：平台与租户数据模型

**目标：** 先让系统能够表达“平台”和“租户”两层状态，但暂不切换业务读写。

**涉及文件：**

- Create: `intent-hub-backend/intent_hub/platform/models.py`
- Create: `intent-hub-backend/intent_hub/platform/registry.py`
- Create: `intent-hub-backend/intent_hub/platform/workspace.py`
- Modify: `intent-hub-backend/intent_hub/config.py`
- Test: `intent-hub-backend/tests/test_tenant_registry.py`

- [ ] 定义平台级与租户级 Pydantic 模型，至少包含：
  - `TenantRecord`
  - `AccessCodeRecord`
  - `SkillSourceRecord`
  - `TenantWorkspacePaths`
- [ ] 新增平台数据根目录常量：
  - `data/platform/`
  - `data/tenants/<tenant_id>/`
- [ ] 实现 `TenantRegistry`：
  - 从 `tenants.json` 读取租户列表
  - 根据 `tenant_id` 获取租户
  - 根据 `access_code` hash 查找租户
  - 创建 / 轮换 / 禁用 access code
- [ ] 实现 `TenantWorkspaceResolver`：
  - 解析 `settings.json`
  - 解析 `routes.json`
  - 解析 `diagnostics_cache.json`
  - 解析 `skills_index.json`
  - 解析 `imports/`
- [ ] 为默认单租户数据准备迁移兼容入口：
  - 将当前 `data/routes.json`、`data/settings.json`、`data/diagnostics_cache.json` 映射到 `tenant_id=default`
- [ ] 补充单元测试：
  - access code hash 后可查找到租户
  - disabled code 不可通过校验
  - workspace 路径按 tenant_id 稳定生成

**验收标准：**

- 可以在纯文件模式下创建至少一个租户记录。
- 默认租户路径可以被解析。
- 不改动现有 `/predict`、`/routes` 行为。

## 4. 里程碑 2：租户上下文与组件隔离

**目标：** 去掉“全局唯一路由管理器 / Qdrant collection / settings”的假设。

**涉及文件：**

- Create: `intent-hub-backend/intent_hub/tenant/context.py`
- Create: `intent-hub-backend/intent_hub/tenant/components.py`
- Modify: `intent-hub-backend/intent_hub/core/components.py`
- Modify: `intent-hub-backend/intent_hub/services/prediction_service.py`
- Modify: `intent-hub-backend/intent_hub/services/route_service.py`
- Modify: `intent-hub-backend/intent_hub/services/diagnostic_service.py`
- Modify: `intent-hub-backend/intent_hub/services/sync_service.py`
- Test: `intent-hub-backend/tests/test_tenant_components.py`

- [ ] 定义 `TenantContext`：
  - `tenant_id`
  - `tenant_name`
  - `workspace_dir`
  - `routes_path`
  - `settings_path`
  - `diagnostics_cache_path`
  - `qdrant_collection`
- [ ] 实现 `TenantComponentManager`：
  - 基于租户 settings 初始化 encoder
  - 基于租户 collection 初始化 qdrant client
  - 基于租户 routes 初始化 route manager
- [ ] 实现 `TenantComponentRegistry`：
  - `tenant_id -> TenantComponentManager`
  - 支持缓存、惰性初始化、显式 reload
- [ ] 将 `PredictionService` 改造为接收租户组件或 `TenantContext`。
- [ ] 将 `RouteService` 改造为租户级 `routes.json` 读写。
- [ ] 将诊断缓存写入租户 `diagnostics_cache.json`。
- [ ] 将同步逻辑改为按租户 collection 执行。
- [ ] 保留一个兼容入口：
  - 如果未指定租户，默认绑定到 `default`

**验收标准：**

- 两个租户可指向不同的 `routes.json` 与不同 collection。
- 同一次进程内可分别加载两个租户组件实例。
- 默认租户路径下，原功能行为不退化。

## 5. 里程碑 3：`access_code` 统一鉴权与新运行时接口

**目标：** 用租户级 `access_code` 取代旧的 `predict_auth_key` 主路径，并补齐 `/v1/route` / `/v1/me`。

**涉及文件：**

- Create: `intent-hub-backend/intent_hub/services/tenant_auth_service.py`
- Create: `intent-hub-backend/intent_hub/services/runtime_route_service.py`
- Modify: `intent-hub-backend/intent_hub/auth.py`
- Modify: `intent-hub-backend/intent_hub/app.py`
- Create: `intent-hub-backend/intent_hub/api/admin.py`
- Create: `intent-hub-backend/intent_hub/api/tenant.py`
- Test: `intent-hub-backend/tests/test_tenant_auth.py`
- Test: `intent-hub-backend/tests/test_runtime_route_api.py`

- [ ] 区分两类身份：
  - 平台管理员
  - 租户访问者
- [ ] 平台管理员鉴权先保持简单：
  - 继续沿用用户名密码或平台独立配置
- [ ] 实现 `access_code` hash 存储与校验。
- [ ] 新增租户上下文解析装饰器 / 中间件：
  - 从 `Authorization: Bearer <access_code>` 提取 code
  - 查找租户
  - 校验状态
  - 注入 `TenantContext`
- [ ] 新增运行时接口：
  - `POST /v1/route`
  - `GET /v1/me`
- [ ] `POST /v1/route` 响应结构固定为：
  - `tenant_id`
  - `route_key`
  - `score`
  - `matches`
  - `collection`
- [ ] 前期保留 `/predict` 作为兼容接口，但内部复用租户运行时服务。
- [ ] 实现平台管理员接口：
  - `GET /admin/tenants`
  - `POST /admin/tenants`
  - `POST /admin/tenants/{tenant_id}/access-codes`
  - `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate`
  - `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/disable`

**验收标准：**

- 使用不同 `access_code` 请求 `/v1/route` 会命中不同 tenant。
- disabled code 会返回 401。
- `/v1/me` 能返回当前 code 对应租户与 code label。

## 6. 里程碑 4：路由来源与 JSON 导入统一化

**目标：** 明确系统正式路由来源只有 `web_manual` 与 `json_import`，skill 不再直接入路由。

**涉及文件：**

- Create: `intent-hub-backend/intent_hub/services/import_service.py`
- Modify: `intent-hub-backend/intent_hub/models.py`
- Modify: `intent-hub-backend/intent_hub/services/route_service.py`
- Modify: `intent-hub-backend/intent_hub/api/routes.py`
- Test: `intent-hub-backend/tests/test_import_service.py`

- [ ] 为路由模型扩展元数据：
  - `source.type`
  - `source.source_id`
  - `source.import_origin`
  - `source.managed_fields`
  - `sync.status`
  - `sync.last_synced_at`
  - `sync.manual_overrides`
  - `lifecycle_status`
- [ ] 抽出统一 JSON 导入协议：
  - 输入 `routes[]`
  - 支持 `merge` / `replace`
  - 返回 created / updated / removed / conflicts
- [ ] Web 手工创建路由时，写入 `source.type=web_manual`。
- [ ] JSON 导入时，写入 `source.type=json_import`。
- [ ] 将现有 `/routes/import-skill` 改造为仅生成 route JSON draft，不直接产生正式 route。
- [ ] 给导入流程增加冲突校验：
  - `route_key` 冲突
  - `id` 冲突
  - 托管字段覆盖冲突
- [ ] 对 skill 生成但未确认的内容，落入 `imports/` 下的 JSON 草稿而非 `routes.json`。

**验收标准：**

- 手工创建路由与 JSON 导入路由都带来源元数据。
- skill 提炼接口只返回标准 JSON draft。
- `routes.json` 中不再出现“skill 是正式来源类型”的表达。

## 7. 里程碑 5：skill 扫描与 JSON 草稿流水线

**目标：** 完成 `skills/` 目录扫描、`SKILL.md` 提炼、草稿生成、统一导入。

**涉及文件：**

- Create: `intent-hub-backend/intent_hub/services/skill_scan_service.py`
- Create: `intent-hub-backend/intent_hub/services/skill_json_generation_service.py`
- Modify: `intent-hub-backend/intent_hub/services/route_service.py`
- Modify: `intent-hub-backend/intent_hub/config.py`
- Create: `intent-hub-backend/tests/test_skill_scan_service.py`

- [ ] 定义 `skills_index.json` 结构：
  - `skill_path`
  - `skill_hash`
  - `json_hash`
  - `draft_file`
  - `route_id`
  - `status`
  - `last_scanned_at`
  - `last_synced_at`
- [ ] 实现 skill source 配置：
  - 一个租户可配置多个 skills 根目录
  - 每个 source 可配置 `draft` / `apply`
- [ ] 实现扫描逻辑：
  - 识别每个子目录下的 `SKILL.md`
  - 计算 hash
  - 对比索引
  - 识别新增 / 更新 / 删除
- [ ] 复用现有 LLM prompt 能力，但输出必须是标准 route JSON draft。
- [ ] 为每个 skill 生成 JSON 草稿文件：
  - 存入 `data/tenants/<tenant_id>/imports/skills/...`
- [ ] 更新索引并记录来源元数据：
  - `import_origin=skill_scan`
- [ ] `draft` 模式下：
  - 只生成草稿与索引
- [ ] `apply` 模式下：
  - 草稿生成后自动走统一 JSON 导入服务
- [ ] 对被删除的 `SKILL.md`：
  - 标记为 `stale`
  - 不直接删除正式 route

**验收标准：**

- 给定一个 skills 目录，可以发现多个 `SKILL.md` 并生成多个 JSON 草稿。
- 修改单个 `SKILL.md` 后，只更新对应草稿与索引项。
- 删除 `SKILL.md` 后，系统只标记 `stale`。

## 8. 里程碑 6：Web 控制台多租户化

**目标：** 支持平台管理员视图、租户 access code 登录、skills 草稿确认。

**涉及文件：**

- Modify: `intent-hub-frontend/src/api/index.ts`
- Modify: `intent-hub-frontend/src/router/index.ts`
- Modify: `intent-hub-frontend/src/views/Login.vue`
- Modify: `intent-hub-frontend/src/views/AgentList.vue`
- Modify: `intent-hub-frontend/src/views/Settings.vue`
- Modify: `intent-hub-frontend/src/views/Diagnostics.vue`
- Create: `intent-hub-frontend/src/views/admin/TenantList.vue`
- Create: `intent-hub-frontend/src/views/admin/TenantDetail.vue`
- Create: `intent-hub-frontend/src/views/tenant/SkillSources.vue`
- Create: `intent-hub-frontend/src/views/tenant/SkillDrafts.vue`

- [ ] 改造登录页：
  - 管理员登录入口
  - `access_code` 登录入口
- [ ] Axios 拦截器改造：
  - 管理员 session / token
  - 租户 session / token
  - 运行时测试 code
- [ ] 租户页 API 统一切换到 `/tenant/*`。
- [ ] 新增平台管理员页面：
  - 租户列表
  - access code 管理
  - skill source 管理
- [ ] 新增租户页：
  - skill source 列表
  - scan 按钮
  - JSON 草稿列表
  - 单条确认导入 / 批量应用
- [ ] 路由列表页展示：
  - `source.type`
  - `sync.status`
  - `lifecycle_status`
- [ ] 设置页只展示租户级设置，不再暴露平台级敏感项。

**验收标准：**

- 租户可使用 `access_code` 登录控制台。
- 管理员可管理租户与 code。
- 租户可看到 skill JSON 草稿并确认导入。

## 9. 里程碑 7：SDK / CLI MVP

**目标：** 提供真正的“一行命令 / 一次调用”接入。

**涉及文件：**

- Create: `intent-hub-backend/sdk/python/intent_hub/__init__.py`
- Create: `intent-hub-backend/sdk/python/intent_hub/client.py`
- Create: `intent-hub-backend/sdk/python/pyproject.toml`
- Create: `intent-hub-backend/cli/intent_hub_cli.py`
- Modify: `intent-hub-backend/pyproject.toml`
- Update: `intent-hub-backend/docs/API.md`

- [ ] 定义 Python SDK MVP：
  - `IntentHubClient(endpoint, access_code)`
  - `route(text)`
  - `whoami()`
- [ ] 定义 CLI MVP：
  - `intent-hub login --endpoint --code`
  - `intent-hub whoami`
  - `intent-hub route "<text>"`
  - `intent-hub route "<text>" --json`
  - `intent-hub skills scan`
  - `intent-hub skills apply`
- [ ] 定义本地配置文件位置与结构。
- [ ] 确保 CLI 输出适配：
  - shell
  - PowerShell `ConvertFrom-Json`
  - opencode / agent 系统子进程调用
- [ ] README / API 文档补充集成示例：
  - Python
  - curl
  - PowerShell

**验收标准：**

- 一行命令可返回 `route_key`。
- SDK / CLI 统一复用 `/v1/route`。
- PowerShell 管道消费 JSON 无需额外转义处理。

## 10. 数据迁移计划

- [ ] 新增一次性迁移脚本：
  - 创建 `tenant_id=default`
  - 将旧 `data/routes.json` 迁入 `data/tenants/default/routes.json`
  - 将旧 `data/settings.json` 迁入 `data/tenants/default/settings.json`
  - 将旧 `data/diagnostics_cache.json` 迁入 `data/tenants/default/diagnostics_cache.json`
  - 生成 `data/platform/tenants.json`
- [ ] 将旧 `QDRANT_COLLECTION` 迁移为默认租户 collection。
- [ ] 保留兼容读取：
  - 若新目录不存在，启动时可提示并引导迁移
- [ ] 提供回滚策略：
  - 原始单租户文件在迁移前备份为 `.bak`

## 11. 测试策略

### 11.1 后端单元测试

- [ ] `test_tenant_registry.py`
  - 租户加载
  - access code 查找
  - code rotate / disable
- [ ] `test_tenant_auth.py`
  - bearer code 成功
  - disabled code 失败
  - unknown code 失败
- [ ] `test_tenant_components.py`
  - 多租户组件隔离
  - workspace 路径隔离
- [ ] `test_import_service.py`
  - `web_manual`
  - `json_import`
  - 冲突处理
- [ ] `test_skill_scan_service.py`
  - skills 扫描
  - hash 更新
  - stale 标记
- [ ] `test_runtime_route_api.py`
  - `/v1/route`
  - `/v1/me`

### 11.2 前端验证

- [ ] 管理员登录
- [ ] 租户 access code 登录
- [ ] 查看租户路由列表
- [ ] skill 扫描并生成草稿
- [ ] 草稿确认导入
- [ ] `npm run build`

### 11.3 集成验证

- [ ] 默认租户兼容旧数据运行
- [ ] 新建第二租户并配置独立 collection
- [ ] 两个租户分别调用 `/v1/route`
- [ ] CLI `route` 命令拿到正确 `route_key`

## 12. 风险与控制

- 风险 1：全局 `Config` 与租户级 settings 混用。
  - 控制：先明确哪些配置是平台级，哪些是租户级，并在代码层分文件承载。
- 风险 2：现有服务层大量隐式依赖全局单例。
  - 控制：先引入 `TenantContext`，逐步改造服务构造参数，不要一次性重写。
- 风险 3：skill 自动导入污染生产路由。
  - 控制：默认 `draft`，正式导入必须走 JSON import。
- 风险 4：前端登录态混乱。
  - 控制：管理员态和租户态分存储键、分路由守卫。
- 风险 5：Qdrant collection 切换带来数据错写。
  - 控制：所有向量写入都从 `TenantContext.collection_name` 取值，禁止直接读全局 `Config.QDRANT_COLLECTION`。

## 13. 推荐实施顺序

1. 先做里程碑 1 和 2，把数据模型和上下文边界立住。
2. 再做里程碑 3，打通 `access_code` 与 `/v1/route`，让运行时先可用。
3. 接着做里程碑 4 和 5，把 route source 与 skill -> JSON -> import 流水线统一。
4. 然后做里程碑 6，补控制台。
5. 最后做里程碑 7，输出 SDK / CLI MVP。

## 14. MVP 截止线

如果要尽快交付第一版可用系统，建议 MVP 截止到以下能力：

- 多租户 registry
- 每租户独立 workspace
- 每租户独立 collection
- `access_code` 统一鉴权
- `/v1/route`
- `/v1/me`
- Web `access_code` 登录
- 单个租户 skills 目录扫描
- `SKILL.md -> JSON draft -> 手工确认导入`

以下内容可以延后：

- 多 skills source 高级策略
- 自动 `apply` 模式
- `/v1/dispatch`
- 完整 Python 包发布

## 15. 完成定义

满足以下条件才算本计划实施完成：

- 平台管理员可创建租户、维护多个 `access_code`
- 每个 `access_code` 能登录 Web，也能访问 `/v1/route`
- 每个租户有独立 `routes.json`、`settings.json`、`diagnostics_cache.json`、`skills_index.json`
- skill 只能作为 JSON 导入上游，不作为正式 route source
- 正式 route source 只有 `web_manual` 与 `json_import`
- 一个 PowerShell / shell 一行命令可稳定拿到 `route_key`

