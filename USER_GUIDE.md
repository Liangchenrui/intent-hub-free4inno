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

### 5.3 同步索引

```bash
curl -X POST http://intenthub.free4inno.com/tenant/reindex \
  -H "Authorization: Bearer <access_code>" \
  -H "Content-Type: application/json" \
  -d "{\"force_full\":false}"
```

## 6. 独立 CLI 包

如果你只需要访问远程 Intent Hub，不需要本地部署后端，请使用 `intent-hub-cli`。

使用 CLI 或 Python SDK 时，请直接安装已发布版本：

```bash
pip install intent-hub-cli==0.1.4
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
pip install intent-hub-cli==0.1.4
```

### 6.1 CLI 用法

CLI 安装后可执行名有两个：

- `intent-hub`
- `intenthub`

两者作用完全相同，下面统一使用 `intent-hub` 举例。

```bash
intent-hub login --endpoint http://192.168.33.1:31627 --code <access_code>
intent-hub whoami
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json
intent-hub route --dispatch "帮我整理 wiki"
intent-hub route --dispatch "帮我整理 wiki" --json
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
intent-hub skills scan --source-path D:/skills --source-id src_001
intent-hub sync
intent-hub sync --force-full --json
intent-hub sync --route-ids 12,15 --json
```

CLI 会把登录信息保存在 `~/.intent-hub/config.json`。除了 `login` 之外，其余命令都会优先读取这个配置文件，因此通常先执行一次登录即可。

#### 6.1.1 `login`

用于保存远端 Intent Hub 地址和租户 `access_code`，不会立即调用服务端验证。

```bash
intent-hub login --endpoint http://intenthub.free4inno.com/ --code <access_code>
```

参数说明：

- `--endpoint`：必填。Intent Hub 服务地址，例如 `http://intenthub.free4inno.com/`。后续 CLI 会基于这个地址调用 `/v1/*` 和 `/tenant/*` 接口。
- `--code`：必填。租户访问码，即 `access_code`。

执行结果：

- 成功时输出 `Saved login config`
- 会覆盖本地已有的 `~/.intent-hub/config.json`

适用场景：

- 首次使用 CLI
- 切换到新的环境，例如从测试环境切到生产环境
- 切换到新的租户访问码

#### 6.1.2 `whoami`

用于验证当前配置的 `endpoint` 和 `access_code` 是否可用，并查看当前租户身份。

```bash
intent-hub whoami
```

参数说明：

- 无命令参数。

输出说明：

- 返回 JSON 字符串
- 通常包含当前 `tenant_id`、`tenant_name`、`code_id`、`code_label`、`collection` 等字段

常见用途：

- 登录后快速确认当前 CLI 正在使用哪个租户
- 排查 401 或 access code 配错问题

#### 6.1.3 `route`

用于调用运行时路由判定接口 `/v1/route`。

```bash
intent-hub route "帮我整理 wiki"
intent-hub route "帮我整理 wiki" --json
```

参数说明：

- `text`：必填。要判定的用户输入文本，这是位置参数，不需要写成 `--text`。
- `--json`：可选。默认不传。传入后输出完整 JSON；不传时只输出预测结果里的 `route_key`。

输出行为：

- 默认输出最核心的 `route_key`
- 使用 `--json` 时，通常会返回完整响应，包括 `score`、`matches`、`collection` 等字段

适用场景：

- Shell 脚本中只关心路由 key 时，直接用默认输出
- 调试模型打分和候选结果时，使用 `--json`

#### 6.1.4 `route --dispatch`

用于在 `route` 命令下直接调用运行时 dispatch 接口 `/v1/dispatch`。

```bash
intent-hub route --dispatch "帮我整理 wiki"
intent-hub route --dispatch "帮我整理 wiki" --json
```

参数说明：

- `--dispatch`：可选。传入后，CLI 底层直接调用 `/v1/dispatch`，而不是 `/v1/route`。
- `text`：必填。要提交给 dispatch 的用户输入文本。
- `--json`：可选。默认不传。传入后输出完整 JSON；不传时只输出响应中的 `route_key`。

输出行为：

- 默认只打印 `route_key`
- 使用 `--json` 时可看到完整 dispatch 响应，包括 `matches`、`dispatch` 建议等字段

注意：

- 当前系统中的 dispatch 只返回建议，不会真的执行外部工具
- 如果你要排查为什么某条请求没有命中预期技能，建议加 `--json`

#### 6.1.5 `skills scan`

用于扫描本地 skill 目录，递归收集其中的 `SKILL.md`，然后把内容上传到后端 `/tenant/skill-sources/scan`，直接把新的 skill 关联进路由实体。

```bash
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
intent-hub skills scan --source-path D:/skills --source-id src_001
```

参数说明：

- `--source-path`：必填。本地目录路径。CLI 会递归查找该目录下所有 `SKILL.md`。
- `--source-label`：可选。上传时附带的 source 名称。通常在首次上传某个本地目录、希望后端自动创建新的 source 时使用。
- `--source-id`：可选。已有 source 的唯一标识。传入后，后端会尝试把本次上传结果归属到这个已有 source，而不是新建一个。

扫描规则：

- CLI 会递归查找 `--source-path` 下的所有 `SKILL.md`
- 每个 skill 会上传三个核心字段：`skill_name`、`relative_path`、`content`
- `skill_name` 默认取 `SKILL.md` 所在文件夹名称
- `relative_path` 是相对于 `--source-path` 的相对路径，例如 `wiki_builder/SKILL.md`

返回结果：

- 命令输出完整 JSON
- 常见字段包括 `source_id`、`discovered`、`added`、`updated`、`errors`

参数组合建议：

- 首次扫描某个本地目录：只传 `--source-path`，或同时传 `--source-label`
- 重传到已有 source：优先传 `--source-id`
- 如果你希望前后端界面里显示更友好的名称，可以同时传 `--source-label`

注意：

- `--source-path` 必须是本地真实存在的目录
- 目录中没有 `SKILL.md` 时，上传结果通常会是空列表或 `discovered=0`
- 某个 `SKILL.md` 读不到或内容为空时，CLI 会把错误追加到输出 JSON 的 `errors` 字段

#### 6.1.6 `sync`

用于触发后端索引同步。没有单独的 `dispatch` 或 `skills apply` 命令后，`sync` 负责把路由层变化同步到向量索引层。

```bash
intent-hub sync
intent-hub sync --force-full --json
intent-hub sync --route-id 12 --json
intent-hub sync --route-ids 12,15 --json
```

参数说明：

- `--force-full`：可选。执行全量重建，对应后端 `/tenant/reindex` 且 `force_full=true`。
- `--route-id`：可选。同步单个路由。
- `--route-ids`：可选。同步多个路由 id，逗号分隔，例如 `12,15,18`。
- `--json`：可选。输出完整 JSON；不传时默认输出后端返回的 `message`。

约束：

- `--force-full` 不能和 `--route-id`、`--route-ids` 同时使用。
- 未传路由 id 时，`sync` 默认执行增量 reindex。

#### 6.1.7 命令使用建议

- 只想保存登录信息：使用 `login`
- 想确认当前 access code 是否可用：使用 `whoami`
- 想快速得到预测到的路由 key：使用 `route`
- 想查看更完整的运行时建议：使用 `route --dispatch --json`
- 想从本地 skills 目录直接补充路由实体：使用 `skills scan`
- 想把路由变化同步到索引层：使用 `sync`

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
print(client.reindex())
print(client.sync_routes([12, 15]))

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

### 8.4 `route --dispatch` 没有执行工具

这是当前设计，dispatch 只返回建议。
