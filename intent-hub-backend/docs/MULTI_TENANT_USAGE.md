# Intent Hub 多租户使用说明

## 1. 适用版本

本文档对应 `multi-tenant access_code + skills` 方案实现，核心能力包含：

- 多租户隔离工作区与 collection
- `access_code` 统一用于运行时与租户控制面
- 运行时接口：`/v1/me`、`/v1/route`、`/v1/dispatch`
- skills 扫描与 JSON 草稿导入
- CLI / Python SDK 最小可用接入

## 2. 数据目录

平台与租户数据目录约定：

```text
data/
  platform/
    tenants.json
    admin_settings.json
  tenants/
    <tenant_id>/
      settings.json
      routes.json
      diagnostics_cache.json
      skills_index.json
      imports/
```

## 3. 管理员操作

管理员使用平台 API Key 调用 `/admin/*`：

1. 创建租户：

```bash
curl -X POST http://127.0.0.1:5000/admin/tenants \
  -H "Authorization: Bearer <admin_api_key>" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"team_alpha\",\"name\":\"Team Alpha\"}"
```

2. 创建 access code：

```bash
curl -X POST http://127.0.0.1:5000/admin/tenants/team_alpha/access-codes \
  -H "Authorization: Bearer <admin_api_key>" \
  -H "Content-Type: application/json" \
  -d "{\"label\":\"cli\"}"
```

3. 轮换/禁用 code：

- `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/rotate`
- `POST /admin/tenants/{tenant_id}/access-codes/{code_id}/disable`

## 4. 租户运行时调用

租户用 `access_code` 调用运行时接口：

1. 查看当前身份：

```bash
curl http://127.0.0.1:5000/v1/me \
  -H "Authorization: Bearer <access_code>"
```

2. 路由判定：

```bash
curl -X POST http://127.0.0.1:5000/v1/route \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

3. Dispatch 建议（MVP 不执行工具，仅返回建议）：

```bash
curl -X POST http://127.0.0.1:5000/v1/dispatch \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

## 5. Skills 流水线

租户控制面接口均使用 `access_code`：

1. 配置 skill source：`POST /tenant/skill-sources`
2. 触发扫描：`POST /tenant/skill-sources/scan`
3. 查看草稿索引：`GET /tenant/skill-drafts`
4. 应用草稿：`POST /tenant/skill-drafts/apply`

`sync_mode` 说明：

- `draft`：只生成草稿，不写入正式 routes
- `apply`：扫描后自动走 JSON 导入

## 6. CLI 用法

```bash
intent-hub login --endpoint http://127.0.0.1:5000 --code <access_code>
intent-hub whoami
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json
intent-hub dispatch "帮我整理 wiki"
intent-hub dispatch "帮我整理 wiki" --json
intent-hub skills scan
intent-hub skills apply --draft-file D:/.../imports/skills/src_001/wiki_builder.json
```

## 7. Python SDK 用法

```python
from intent_hub import IntentHubClient

client = IntentHubClient(
    endpoint="http://127.0.0.1:5000",
    access_code="ih_live_team_alpha_xxx",
)

print(client.whoami())
print(client.route("帮我整理 wiki"))
print(client.dispatch("帮我整理 wiki"))
```
