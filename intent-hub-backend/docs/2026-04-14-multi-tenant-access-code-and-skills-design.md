# Intent Hub 多租户 Access Code 与 Skills 自动导入设计

## 1. 背景与目标

Intent Hub 当前已经具备以下基础能力：

- 基于向量相似度的意图路由
- 路由实体维护，包括名称、描述、语料句、负例、阈值
- 基于 `SKILL.md` 内容生成单个路由草稿
- Web 管理界面
- Flask API

当前系统的主要问题不是路由算法本身，而是产品形态偏“单实例后台”：

- 配置是全局静态的
- 组件实例是全局单例的
- 所有路由和设置共用一份运行时数据
- `/predict` 适合单系统调用，但不适合多系统、多租户、多入口集成
- 仅支持按请求生成单个 skill 对应的路由 JSON 草稿，不支持目录级自动发现和持续同步

本设计的目标是将 Intent Hub 升级为一个可嵌入、可集成、可多租户运行的意图路由控制面与运行时系统。

核心目标如下：

1. 引入多租户模型，每个租户通过一个或多个 `access_code` 访问系统。
2. `access_code` 同时可用于：
   - SDK / CLI 调用
   - 运行时 API 鉴权
   - 登录 Web 管理界面
3. 每个租户绑定一个独立的 Qdrant collection。
4. 每个租户独享自己的 routes、settings、diagnostics cache。
5. 支持为租户指定一个 `skills/` 目录，自动识别其下每个子目录中的 `SKILL.md`，先经 LLM 提炼为标准路由 JSON，再通过统一 JSON 导入链路生成或更新对应路由实体。
6. 提供统一的运行时 contract，使用户可以用一行命令或一个 SDK 调用完成意图 skill 路由。

## 2. 非目标

本次设计暂不覆盖以下内容：

- 完整的 SaaS 级组织、成员、角色、细粒度权限控制
- 多用户协作审批流
- 插件市场和远程技能仓库
- 复杂计费系统
- 将所有 skill 自动执行为真正的 agent runtime

本次先聚焦于“多租户控制面 + 统一接入面 + skills 自动导入 + 运行时路由”。

## 3. 设计原则

### 3.1 控制面与运行面分离

- 控制面负责维护租户、access code、routes、settings、skills 导入状态、诊断结果。
- 运行面负责根据输入文本和租户上下文执行路由判定，并返回稳定结果。

### 3.2 租户是一级边界

任何运行时请求都必须先解析到租户上下文，再决定：

- 用哪个 collection
- 读哪份 routes
- 读哪份 settings
- 用哪份 diagnostics cache

### 3.3 路由实体是系统核心资产

系统的重要价值不只是分类，更是高质量地维护每个路由实体的：

- `name`
- `route_key`
- `description`
- `utterances`
- `negative_samples`
- 阈值配置
- 来源与同步状态

### 3.4 Skill 应作为 JSON 导入的上游输入

`SKILL.md` 不应成为独立的正式路由来源类型，而应作为 JSON 导入的上游输入材料。系统应支持扫描目录、调用 LLM 提炼核心信息、生成标准路由 JSON，并统一走 JSON 导入链路。

### 3.5 接入方式统一

Web、SDK、CLI、PowerShell、opencode 等调用方应共享同一套运行时语义：

- 使用同一种 `access_code`
- 获得同一种路由结果结构
- 能稳定依赖 `route_key`

## 4. 总体方案

采用“方案 2：标准方案”。

系统拆分为三层：

1. `intent-hub-core`
   - 多租户路由内核
   - 租户上下文解析
   - 路由判定
   - skills 扫描、JSON 生成与导入
2. `intent-hub-server`
   - Web 管理界面与 HTTP API
   - 平台管理员接口
   - 租户管理接口
   - 运行时路由接口
3. `intent-hub-sdk` / `intent-hub-cli`
   - 用户侧接入面
   - 一行命令调用
   - PowerShell / shell / agent 系统集成

系统定位从“一个单体管理后台”升级为“多租户意图路由控制面 + 统一运行时”。

## 5. 核心概念

### 5.1 Tenant

租户是系统的一级隔离边界。一个租户独享：

- 一个 Qdrant collection
- 一份 routes
- 一份 settings
- 一份 diagnostics cache
- 一组 `access_code`
- 零个或多个 skills 扫描目录

### 5.2 Access Code

`access_code` 是租户级访问凭证，不再只是传统意义上的 API key。它有三个用途：

1. 运行时 API 调用凭证
2. CLI / SDK 配置凭证
3. Web 管理界面登录凭证

系统应支持：

- 创建 access code
- 禁用 access code
- 轮换 access code
- 记录最后使用时间
- 对 access code 存 hash，不明文持久化

### 5.3 Tenant Workspace

每个租户对应一个工作区目录，保存租户状态。

### 5.4 Skill Source

租户可以配置一个或多个 `skills/` 根目录。系统会扫描这些目录下的每个子目录，寻找 `SKILL.md`，并将其转译为标准路由 JSON。

### 5.5 Route Source

每个路由实体的正式来源元数据收敛为两类：

- `web_manual`
- `json_import`

其中 skill 扫描和单次 skill 文本提炼生成的路由，正式来源都记为 `json_import`，只是附带额外导入元数据表明该 JSON 来源于某个 `SKILL.md`。

来源元数据用于后续的同步策略、冲突提示、人工覆盖保护。

## 6. 租户与鉴权模型

## 6.1 角色模型

本设计采用两层身份：

1. 平台管理员
   - 管理所有租户
   - 创建/停用/轮换 access code
   - 查看平台级状态

2. 租户访问者
   - 持有某个租户的 access code
   - 只能访问本租户的路由、设置、诊断和 skills 导入

### 6.2 鉴权方式

#### 运行时 API

调用方使用：

```http
Authorization: Bearer <access_code>
```

后端流程：

1. 读取 `access_code`
2. 查找匹配的租户
3. 校验状态是否为 active
4. 构造 `TenantContext`
5. 使用租户自己的 collection、routes、settings 执行请求

#### Web 登录

Web 提供两个入口：

1. 平台管理员登录
2. 租户 access code 登录

租户登录流程：

1. 用户输入 `access_code`
2. 后端校验租户
3. 后端签发租户 session / JWT
4. Web 后续请求使用 session / JWT，而不是长时间暴露裸 `access_code`

#### CLI / SDK

CLI 与 SDK 直接配置 `access_code`，无需再引入额外登录步骤。

### 6.3 一个租户多个 access code

系统应支持一个租户配置多个 access code，例如：

- 生产调用 code
- 本地开发 code
- Web 管理 code

不同 code 共享同一个租户工作区和 collection，但可以附带标签与用途说明。

## 7. 数据模型设计

### 7.1 Platform 数据

平台级数据建议存放在：

```text
data/platform/
```

核心文件：

```text
data/platform/admin_settings.json
data/platform/tenants.json
```

### 7.2 Tenant Workspace

租户数据建议存放在：

```text
data/tenants/<tenant_id>/
```

每个租户目录结构：

```text
data/tenants/team_alpha/
  settings.json
  routes.json
  diagnostics_cache.json
  skills_index.json
  imports/
```

### 7.3 Tenant 元数据结构

示例：

```json
{
  "tenant_id": "team_alpha",
  "name": "Team Alpha",
  "status": "active",
  "qdrant_collection": "intent_hub_team_alpha",
  "access_codes": [
    {
      "code_id": "ac_001",
      "label": "default",
      "code_hash": "sha256:...",
      "status": "active",
      "created_at": "2026-04-14T10:00:00Z",
      "last_used_at": "2026-04-14T12:30:00Z"
    }
  ],
  "skill_sources": [
    {
      "source_id": "src_001",
      "path": "D:/skills/team_alpha",
      "enabled": true,
      "sync_mode": "scan"
    }
  ]
}
```

### 7.4 Route 元数据扩展

`routes.json` 中每个路由除已有字段外，建议新增：

```json
{
  "id": 12,
  "name": "Obsidian Wiki Builder",
  "route_key": "obsidian.wiki.build",
  "description": "根据原始材料构建或更新 wiki 知识库",
  "utterances": ["整理 wiki", "从 raw 构建知识库"],
  "negative_samples": [],
  "score_threshold": 0.82,
  "negative_threshold": 0.95,
  "source": {
    "type": "json_import",
    "source_id": "src_001",
    "skill_path": "D:/skills/team_alpha/obsidian-wiki-builder/SKILL.md",
    "skill_hash": "sha256:...",
    "import_origin": "skill_scan",
    "managed_fields": ["name", "description", "utterances"]
  },
  "sync": {
    "status": "synced",
    "last_synced_at": "2026-04-14T12:00:00Z",
    "manual_overrides": ["score_threshold"]
  }
}
```

这样系统可以知道该路由是否来自 skill 扫描，以及哪些字段允许被自动更新。

## 8. Skills 目录自动识别与导入设计

## 8.1 目标

系统应支持为租户配置一个 `skills/` 目录，自动识别目录下每个子目录中的 `SKILL.md` 文件，并先为每个 skill 生成标准路由 JSON，再统一导入为路由实体。

例如：

```text
skills/
  obsidian-raw-to-wiki/
    SKILL.md
  dogfood/
    SKILL.md
  frontend-design/
    SKILL.md
```

扫描后自动生成三个候选 JSON 导入项，并进一步形成三个路由候选。

### 8.2 扫描规则

对每个已启用的 `skill_source.path` 执行以下规则：

1. 扫描第一层和可配置深度的子目录。
2. 如果子目录内存在 `SKILL.md`，则视为一个 skill 单元。
3. 计算 `SKILL.md` 文件 hash。
4. 查找该 skill 是否已建立过导入映射。
5. 若不存在映射，则生成新的 JSON 草稿。
6. 若已存在映射但 hash 变化，则触发更新策略。

### 8.3 Skill 到 JSON 再到路由的生成流程

每个 `SKILL.md` 的处理流程如下：

1. 读取 `SKILL.md`
2. 提取：
   - skill 名称
   - 描述
   - 触发词
   - 典型场景
3. 调用现有 LLM 生成逻辑，生成标准路由 JSON，至少包含：
   - `name`
   - `route_key`
   - `description`
   - `utterances`
4. 对 JSON 做规范化与校验
5. 将 JSON 按统一导入协议写入草稿或导入队列
6. 通过统一 JSON 导入链路生成或更新路由

这样设计的好处是：

1. skill 导入与普通 JSON 导入共用同一套验证、冲突检测、落库逻辑
2. skill 识别阶段与路由写入阶段解耦，便于审阅、回放和排错

### 8.4 两种导入模式

建议支持两种模式：

1. `draft`
   - 扫描后只生成 JSON 草稿
   - 需要租户在 Web 上确认后再执行 JSON 导入并落入 `routes.json`

2. `apply`
   - 扫描后自动生成 JSON 并执行导入
   - 适合稳定的内部 skill 仓库

默认推荐 `draft`，避免 skill 文档波动直接污染生产路由。

### 8.5 更新策略

当同一个 `SKILL.md` 发生变化时，系统需要决定如何更新对应 JSON 导入结果及其最终路由。

建议规则：

1. 自动托管字段默认包括：
   - `name`
   - `description`
   - `utterances`

2. 默认不自动覆盖：
   - `route_key`
   - `score_threshold`
   - `negative_threshold`
   - `negative_samples`

3. 若路由存在人工修改记录，则在 Web 上标记“有变更待合并”

4. 对于路由不存在时，直接生成新的 JSON 草稿

### 8.6 唯一性与冲突

可能出现以下冲突：

- 两个不同 skill 被推断出相同的 `route_key`
- skill 名称和现有人工路由高度重复
- 自动生成的 utterances 与其他路由严重重叠

处理策略：

1. `route_key` 冲突时不自动覆盖，生成冲突告警
2. 名称相似时允许创建，但在控制台标记“疑似重复”
3. 自动导入后应触发增量诊断，提示潜在语义重叠

### 8.7 Skill 索引

系统应为每个租户维护 `skills_index.json`，用于记录：

- 已发现的 skill
- `SKILL.md` 路径
- 当前 hash
- 最近生成的 JSON hash
- 关联 route_id
- 最近扫描时间
- 最近同步结果

示例：

```json
{
  "items": [
    {
      "source_id": "src_001",
      "skill_path": "D:/skills/team_alpha/dogfood/SKILL.md",
      "skill_hash": "sha256:...",
      "json_hash": "sha256:...",
      "route_id": 25,
      "status": "synced",
      "last_scanned_at": "2026-04-14T12:10:00Z",
      "last_synced_at": "2026-04-14T12:11:00Z"
    }
  ]
}
```

## 9. 运行时接口设计

运行时接口面向 SDK、CLI、PowerShell、opencode 等调用方。

### 9.1 Route 接口

```http
POST /v1/route
Authorization: Bearer <access_code>
```

请求：

```json
{
  "text": "帮我整理 wiki 目录"
}
```

响应：

```json
{
  "tenant_id": "team_alpha",
  "route_key": "obsidian.wiki.build",
  "score": 0.93,
  "matches": [
    {
      "id": 12,
      "name": "Obsidian Wiki Builder",
      "route_key": "obsidian.wiki.build",
      "score": 0.93
    }
  ],
  "collection": "intent_hub_team_alpha"
}
```

### 9.2 Dispatch 接口

本次设计建议预留：

```http
POST /v1/dispatch
```

初期可以只返回匹配路由和执行建议，不强制要求当前版本完成真实执行器框架。

### 9.3 Me 接口

```http
GET /v1/me
```

返回当前 access code 所属租户、code label、可用能力等信息，便于 SDK / CLI 诊断。

## 10. 控制面接口设计

### 10.1 平台管理员接口

```text
GET    /admin/tenants
POST   /admin/tenants
PUT    /admin/tenants/{tenant_id}
POST   /admin/tenants/{tenant_id}/access-codes
POST   /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate
POST   /admin/tenants/{tenant_id}/access-codes/{code_id}/disable
POST   /admin/tenants/{tenant_id}/skill-sources
```

### 10.2 租户管理接口

```text
GET    /tenant/routes
POST   /tenant/routes
PUT    /tenant/routes/{route_id}
DELETE /tenant/routes/{route_id}

GET    /tenant/settings
POST   /tenant/settings

GET    /tenant/diagnostics/overlap
POST   /tenant/skills/scan
GET    /tenant/skills/index
POST   /tenant/skills/generate-json
POST   /tenant/skills/apply
```

## 11. SDK 与 CLI 设计

### 11.1 Python SDK

推荐接口：

```python
from intent_hub import IntentHubClient

client = IntentHubClient(
    endpoint="https://intent-hub.example.com",
    access_code="ih_live_xxxxx",
)

result = client.route("帮我整理这个 wiki")
print(result.route_key)
```

SDK 支持两种模式：

1. `remote`
   - 调用远端 Intent Hub HTTP API
2. `local`
   - 直接使用本地 core 与 tenant workspace

第一阶段优先实现 `remote`。

### 11.2 CLI

推荐命令：

```bash
intent-hub login --endpoint https://intent-hub.example.com --code ih_live_xxxxx
intent-hub whoami
intent-hub route "帮我整理这个 wiki"
intent-hub route "帮我整理这个 wiki" --json
intent-hub skills scan
intent-hub skills apply --source src_001
```

本地配置文件建议：

```toml
endpoint = "https://intent-hub.example.com"
access_code = "ih_live_xxxxx"
```

### 11.3 PowerShell 集成

PowerShell 不需要专门 SDK，只需 CLI 支持即可：

```powershell
$result = intent-hub route "帮我整理 wiki" --json | ConvertFrom-Json
$result.route_key
```

### 11.4 opencode 与其他 agent 系统

推荐接入方式：

1. 简单接入
   - 直接调用 CLI
2. 深度接入
   - 直接使用 SDK 或 HTTP API
   - 将 `route_key` 作为 tool / skill selector

## 12. 后端架构改造

### 12.1 当前问题

当前实现存在以下耦合：

- 全局静态 `Config`
- 全局单例 `ComponentManager`
- routes 与 settings 为单份全局状态
- `/predict` 与管理接口共享单实例上下文

### 12.2 新的核心对象

建议引入以下对象：

#### PlatformConfig

平台级配置，存放服务默认值与管理员认证配置。

#### TenantRegistry

管理所有租户元数据和 access code 索引。

#### TenantContext

一次请求解析出的租户上下文，例如：

```python
TenantContext(
    tenant_id="team_alpha",
    tenant_name="Team Alpha",
    collection_name="intent_hub_team_alpha",
    workspace_dir=".../data/tenants/team_alpha",
    settings_path=".../settings.json",
    routes_path=".../routes.json",
)
```

#### TenantComponentManager

替代当前全局 `ComponentManager`，按租户管理组件实例。

#### TenantComponentRegistry

维护：

```python
tenant_id -> TenantComponentManager
```

不同租户各自缓存 encoder、qdrant client、route manager。

### 12.3 请求处理流程

以 `/v1/route` 为例：

1. 认证中间件解析 `access_code`
2. `TenantRegistry` 定位到 tenant
3. 构建 `TenantContext`
4. `TenantComponentRegistry` 获取租户组件实例
5. `PredictionService` 在租户上下文中执行路由
6. 返回稳定 JSON 结构

## 13. 路由实体生命周期

### 13.1 路由来源

路由的正式来源收敛为：

- Web 手工创建
- JSON 导入

其中：

- 单次 skill 文本导入，本质上属于“先生成 JSON，再导入”
- skills 目录扫描，本质上也属于“先生成 JSON，再导入”

### 13.2 生命周期状态

建议支持：

- `draft`
- `active`
- `conflict`
- `disabled`
- `stale`

其中：

- `draft` 用于 JSON 导入草稿，包括由 skill 生成出的 JSON 草稿
- `conflict` 表示 route_key 等出现冲突
- `stale` 表示对应 `SKILL.md` 已删除或长期未同步

### 13.3 删除策略

当某个已同步 skill 的 `SKILL.md` 被删除时，不建议立即删除路由，而应：

1. 将路由标记为 `stale`
2. 在控制台提示
3. 允许用户选择：
   - 保留为手工路由
   - 停用
   - 删除

## 14. Web 控制台设计

### 14.1 登录入口

Web 登录页提供两个入口：

1. 平台管理员登录
2. 租户 access code 登录

### 14.2 平台管理员视图

主要页面：

- Tenant 列表
- Access Code 管理
- Skill Source 管理
- 平台运行状态

### 14.3 租户视图

主要页面：

- Route 列表
- Route 编辑器
- Skill 扫描结果
- Skill JSON 草稿
- Skill JSON 草稿确认页
- Diagnostics
- Settings

### 14.4 Skill 扫描页

应显示：

- 扫描到的 skill 数量
- 新增路由候选
- 已更新候选
- 冲突项
- stale 项
- 一键应用 / 逐条确认

## 15. 安全设计

### 15.1 Access Code 存储

服务端不保存明文 code，仅保存 hash。

### 15.2 Web Session

浏览器登录后使用短期 session / JWT，不长期传裸 code。

### 15.3 目录扫描安全

`skill_source.path` 必须由管理员显式配置。系统不能允许租户任意扫描主机任意路径。

建议增加：

- 白名单根目录
- 路径规范化
- 路径存在性检查
- 只读扫描

### 15.4 日志脱敏

日志中不打印完整 access code，仅打印前缀和尾部摘要。

## 16. 迁移方案

### 16.1 第一阶段：多租户基础设施

1. 增加 `TenantRegistry`
2. 增加 `TenantContext`
3. 将现有全局 routes/settings 迁移为默认租户
4. 引入按租户 collection 初始化的组件管理
5. 新增 `/v1/route`

### 16.2 第二阶段：Access Code 与 Web 登录改造

1. 平台管理员体系与租户登录体系分离
2. access code 改为租户级
3. Web 支持 access code 登录
4. CLI / SDK 接入新接口

### 16.3 第三阶段：Skills 自动扫描

1. 增加 `skill_sources`
2. 增加扫描任务与 `skills_index.json`
3. 支持草稿生成与确认落库
4. 支持增量同步与冲突提示

### 16.4 第四阶段：统一 dispatch 运行时

1. 在 route 结果上附加 dispatch metadata
2. CLI 支持 `dispatch`
3. 为 PowerShell / agent 系统提供一行命令接入

## 17. 推荐的最小可用版本

第一版 MVP 建议包含：

1. 多租户模型
2. 每租户独立 collection
3. access code 统一鉴权
4. `/v1/route`
5. CLI `login` / `route`
6. Web access code 登录
7. 单个租户配置一个 `skills/` 目录
8. 扫描目录并生成 route drafts

暂不必在 MVP 中实现：

- 完整 dispatch 执行器
- 多 source 高级合并策略
- 复杂权限控制

## 18. 推荐实施结论

本设计推荐将 Intent Hub 定位为：

“多租户的意图路由控制面与统一运行时。”

其核心形态是：

- 平台管理员维护租户和 access code
- 租户通过 access code 使用 Web、SDK、CLI
- 每个租户独享自己的 Qdrant collection 与路由资产
- 系统可以从租户的 `skills/` 目录自动识别 `SKILL.md`，经 LLM 生成标准路由 JSON，并通过统一 JSON 导入链路生成路由实体
- 路由来源正式收敛为 `web_manual` 与 `json_import`
- 用户侧可以通过一行命令或一次 SDK 调用稳定获得 `route_key`

这一路线比继续增强现有单实例 Flask 后台更合理，也能最大化本系统的可集成性和长期演进空间。
