# Intent Hub User Guide

本文档说明当前仓库中的多租户 Intent Hub 如何启动、登录、管理租户、调用运行时接口，以及如何使用独立 `intent-hub-cli` 包。

## 1. 系统组成

当前仓库包含三部分：

- `intent-hub-backend/`：Flask 后端
- `intent-hub-frontend/`：Vue 管理台
- `intent-hub-cli/`：独立 CLI 和 Python SDK

后端当前主接口分为：

- 管理员接口：`/auth/login`、`/admin/*`
- 租户控制面：`/tenant/*`
- 租户运行时：`/v1/me`、`/v1/route`、`/v1/dispatch`

## 2. 访问方式

普通用户直接访问线上服务：

- Web 入口：`http://intenthub.free4inno.com/`

### 2.1 本地开发

后端：

```bash
cd intent-hub-backend
pip install -e .[dev]
python run.py
```

前端：

```bash
cd intent-hub-frontend
npm install
npm run dev
```

## 3. 鉴权模型

### 3.1 管理员

1. 调用 `/auth/login`
2. 获取管理员 `api_key`
3. 调用 `/admin/*` 时使用 `Authorization: Bearer <api_key>`

### 3.2 租户

1. 使用租户 `access_code`
2. 调用 `/v1/*` 和 `/tenant/*` 时使用 `Authorization: Bearer <access_code>`

## 4. 常用流程

### 4.1 管理员登录

```bash
curl -X POST http://intenthub.free4inno.com/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"admin\",\"password\":\"123456\"}"
```

### 4.2 创建租户

```bash
curl -X POST http://intenthub.free4inno.com/admin/tenants \
  -H "Authorization: Bearer <admin_api_key>" \
  -H "Content-Type: application/json" \
  -d "{\"tenant_id\":\"team_alpha\",\"name\":\"Team Alpha\"}"
```

返回中包含创建时生成的明文 `access_code`。

### 4.3 查询租户身份

```bash
curl http://intenthub.free4inno.com/v1/me \
  -H "Authorization: Bearer <access_code>"
```

### 4.4 路由判定

```bash
curl -X POST http://intenthub.free4inno.com/v1/route \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

### 4.5 Dispatch 建议

```bash
curl -X POST http://intenthub.free4inno.com/v1/dispatch \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"帮我整理 wiki\"}"
```

当前 `dispatch` 只返回建议，不执行真实工具。

## 5. Skills 相关流程

### 5.1 配置 skill source

先通过租户控制面配置技能源目录。

### 5.2 扫描

Skill source 保存的是逻辑元数据，不是后端部署机器上的真实目录。
CLI、Python SDK 和 Web 页面会先在用户本地收集 `SKILL.md`，再把内容上传到后端扫描。

```bash
curl -X POST http://intenthub.free4inno.com/tenant/skill-sources/scan \
  -H "Authorization: Bearer <access_code>"
```

如果通过 Web 页面操作，需要使用浏览器目录选择器重新选择本地目录；浏览器不会把用户完整本地路径直接暴露给后端。

### 5.3 应用草稿

```bash
curl -X POST http://intenthub.free4inno.com/tenant/skill-drafts/apply \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"draft_file\":\"D:/path/to/draft.json\"}"
```

## 6. 独立 CLI 包

如果你只需要访问远程 Intent Hub，不需要本地部署后端，请使用 `intent-hub-cli`。

使用 CLI 或 Python SDK 时，请直接安装已发布版本：

```bash
pip install intent-hub-cli==0.1.0
```

发布前校验：

```bash
cd intent-hub-cli
python -m pip install -e .[dev]
pytest tests -q
python -m build
python -m twine check dist/*
```

发布后用户安装方式：

```bash
pip install intent-hub-cli==0.1.0
```

### 6.1 CLI 用法

```bash
intent-hub login --endpoint http://intenthub.free4inno.com/ --code <access_code>
intent-hub whoami
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json
intent-hub dispatch "帮我整理 wiki"
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
intent-hub skills apply --draft-file D:/path/to/draft.json
```

### 6.2 Python SDK 用法

```python
from intent_hub_cli import IntentHubClient

client = IntentHubClient(
    endpoint="http://intenthub.free4inno.com/",
    access_code="ih_live_team_alpha_xxx",
)

print(client.whoami())
print(client.route("帮我整理 wiki"))
print(client.dispatch("帮我整理 wiki"))

scan_result = client.skills_scan_uploaded(
    source_id=None,
    source_label="team-skills",
    client_path_hint="./skills",
    skills=[
        {
            "relative_path": "wiki-builder/SKILL.md",
            "content": "# wiki-builder\n...",
        }
    ],
)
print(scan_result)
```

`intent-hub-backend/pythonSDK.py` 目前仅保留为仓库内兼容示例入口，实际 SDK 包以 `intent-hub-cli` 为准。

## 7. 运行时数据

当前多租户数据目录结构：

```text
intent-hub-backend/data/
├── platform/
│   ├── admin_settings.json
│   └── tenants.json
└── tenants/
    └── <tenant_id>/
        ├── diagnostics_cache.json
        ├── imports/
        ├── routes.json
        ├── settings.json
        └── skills_index.json
```

## 8. 常见问题

### 8.1 返回 401

检查 `Authorization` 是否为 `Bearer <api_key>` 或 `Bearer <access_code>`。

### 8.2 `/v1/route` 总是回退

检查：

- 当前租户是否已经配置路由
- 路由是否已经建立向量索引
- Embedding 服务和 Qdrant 是否可访问

### 8.3 Skills 扫描没有结果

确认本地目录结构满足 `<source_root>/<skill_name>/SKILL.md`，并且 Web 端重新选择了正确目录或 CLI 传入了正确 `--source-path`。

### 8.4 `dispatch` 没有执行工具

这是当前设计，`dispatch` 只返回建议。
