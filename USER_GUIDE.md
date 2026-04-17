# Intent Hub 多租户系统使用说明

## 1. 系统概述

Intent Hub 当前提供两类能力：

1. 控制面：租户、路由、设置、诊断、skills 扫描与草稿导入。  
2. 运行时：`/v1/me`、`/v1/route`、`/v1/dispatch`（MVP 为“返回分发建议”，不执行真实工具）。

核心特性：

1. 多租户隔离：每个租户独立 `routes.json`、`settings.json`、`diagnostics_cache.json`、`skills_index.json`。  
2. 统一租户凭证：`access_code` 同时用于运行时 API、租户控制面 API、CLI、SDK。  
3. 管理员与租户身份分离：管理员走 `/auth/login` + 管理员 API key；租户走 `access_code`。  

## 2. 目录结构

后端数据目录（`intent-hub-backend/data`）：

```text
data/
  platform/
    admin_settings.json
    tenants.json
  tenants/
    <tenant_id>/
      settings.json
      routes.json
      diagnostics_cache.json
      skills_index.json
      imports/
```

说明：

1. `data/platform/tenants.json`：租户元数据、access code 哈希、skill source 配置。  
2. `data/tenants/<tenant_id>/`：租户业务数据与导入草稿。  

## 3. 启动方式

### 3.1 后端启动

在 `intent-hub-backend` 下：

```bash
python run.py
```

默认监听 `0.0.0.0:5000`（由 `intent_hub/config.py` 决定）。

### 3.2 前端启动（可选）

在 `intent-hub-frontend` 下：

```bash
npm install
npm run dev
```

生产构建：

```bash
npm run build
```

## 4. 鉴权模型

### 4.1 管理员鉴权

1. 调用 `/auth/login`，传用户名密码。  
2. 返回管理员 `api_key`。  
3. 后续调用 `/admin/*` 时带 `Authorization: Bearer <api_key>`。

### 4.2 租户鉴权

1. 使用租户 `access_code`。  
2. 调用 `/v1/*` 与 `/tenant/*` 时带 `Authorization: Bearer <access_code>`。  

## 5. 快速上手流程（推荐）

### 5.1 管理员登录

```bash
curl -X POST http://127.0.0.1:5000/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"123456\"}"
```

返回里拿到 `api_key`。

### 5.2 创建租户

```bash
curl -X POST http://127.0.0.1:5000/admin/tenants \
  -H "Authorization: Bearer <admin_api_key>" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"team_alpha\",\"name\":\"Team Alpha\"}"
```

返回包含初始明文 `access_code`（只在创建/轮换时可见）。

### 5.3 用租户 code 验证身份

```bash
curl http://127.0.0.1:5000/v1/me \
  -H "Authorization: Bearer <access_code>"
```

### 5.4 路由判定

```bash
curl -X POST http://127.0.0.1:5000/v1/route \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

### 5.5 Route 与 Dispatch 区别

1. `POST /v1/route`：只做“意图路由判定”，返回最匹配 `route_key` 与候选列表。  
2. `POST /v1/dispatch`：在 `route` 结果基础上，额外返回 `dispatch` 建议结构（`status/executor/suggestion`）。  
3. 当前版本 `dispatch.status=not_executed`，不会真正执行工具或外部动作。  

### 5.6 Dispatch（MVP）

```bash
curl -X POST http://127.0.0.1:5000/v1/dispatch \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

说明：当前只返回 `dispatch.suggestion`，不执行外部工具。

## 6. API 使用说明

### 6.1 运行时 API（租户）

1. `GET /v1/me`：返回当前 tenant、code 信息、collection。  
2. `POST /v1/route`：返回 `route_key`、`score`、`matches`。  
3. `POST /v1/dispatch`：返回 route 结果 + dispatch 建议。  
4. `POST /predict`：兼容接口，支持 legacy 认证方式。  

### 6.2 管理员 API

1. `GET /admin/tenants`  
2. `POST /admin/tenants`  
3. `POST /admin/tenants/{tenant_id}/access-codes`  
4. `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate`  
5. `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/disable`  

### 6.3 租户控制面 API

1. 路由管理：`/tenant/routes`、`/tenant/routes/{route_id}`、`/tenant/routes/import`。  
2. 设置管理：`GET/POST /tenant/settings`。  
3. 诊断能力：`/tenant/diagnostics/overlap`、`/tenant/diagnostics/umap`、`/tenant/diagnostics/repair`。  
4. skills 管理：`/tenant/skill-sources`、`/tenant/skill-sources/scan`、`/tenant/skill-drafts`、`/tenant/skill-drafts/apply`。  

## 7. Skills 自动导入流程

标准流程：

1. 管理员或租户先配置 skill source：`POST /tenant/skill-sources`。  
2. 扫描：`POST /tenant/skill-sources/scan`。  
3. 系统识别 `SKILL.md`，生成 JSON 结果并执行自动导入策略。  
4. 查看索引：`GET /tenant/skill-drafts`。  
5. 手动应用（可选）：`POST /tenant/skill-drafts/apply`。  

`sync_mode` 说明：

1. `scan`：仅扫描并更新索引。  
2. `apply`：扫描后自动导入；若 `route_key` 已存在则跳过，不覆盖原路由。  

## 8. CLI 使用

先安装独立客户端包，然后登录远程服务：

```bash
cd intent-hub-cli
pip install -e .
intent-hub login --endpoint http://127.0.0.1:5000 --code <access_code>
intent-hub whoami
intenthub route "帮我整理 wiki"
intenthub route "帮我整理 wiki" --json
intenthub dispatch "帮我整理 wiki"
intenthub dispatch "帮我整理 wiki" --json
intent-hub skills scan
intent-hub skills apply --draft-file D:/.../imports/skills/src_001/wiki_builder.json
```

如果需要按标准 pip 分发包形式安装：

```bash
cd intent-hub-cli
python -m pip install -U build
python -m build
pip install dist/intent_hub_cli-0.1.0-py3-none-any.whl
```

后续发布到 PyPI 后，可直接执行：

```bash
pip install intent-hub-cli
```

## 9. Python SDK 使用

```python
from intent_hub_cli import IntentHubClient

client = IntentHubClient(
    endpoint="http://127.0.0.1:5000",
    access_code="ih_live_team_alpha_xxx",
)

print(client.whoami())
print(client.route("帮我整理 wiki"))
print(client.dispatch("帮我整理 wiki"))
```

## 10. 前端使用说明

登录页支持两种入口：

1. 管理员登录（用户名密码）。  
2. 租户 access code 登录。  

常用页面：

1. 管理员视图：租户列表、access code 管理。  
2. 租户视图：路由列表、设置、诊断、skill source 与 skill drafts。  

## 11. 迁移与兼容

已有单租户数据可通过迁移脚本转为默认租户：

`intent-hub-backend/intent_hub/scripts/migrate_single_tenant.py`

迁移目标：

1. 旧 `data/routes.json` -> `data/tenants/default/routes.json`  
2. 旧 `data/settings.json` -> `data/tenants/default/settings.json`  
3. 旧 `data/diagnostics_cache.json` -> `data/tenants/default/diagnostics_cache.json`  
4. 生成 `data/platform/tenants.json`（默认租户）  

## 12. 运维与安全建议

1. 生产环境必须修改默认管理员密码。  
2. `access_code` 仅在创建/轮换时显示，需安全存储。  
3. 建议优先验证扫描结果；`apply` 模式会自动导入新路由，并跳过同 `route_key` 已存在路由。  
4. skill source 路径使用受控目录，避免扫描任意系统路径。  
5. 定期轮换 access code，并停用不用的 code。  

## 13. 常见问题

1. `401 Authentication failed`：检查 `Authorization` 是否为 `Bearer <access_code/api_key>`。  
2. `/v1/route` 总回默认路由：检查租户路由是否已建立向量索引并满足阈值。  
3. skills 扫描无结果：确认目录结构为 `<source_root>/<skill_name>/SKILL.md`。  
4. `dispatch` 没有执行动作：当前版本只返回建议，属预期行为。  
