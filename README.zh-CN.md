# Intent Hub

Intent Hub 是一个多租户意图路由服务仓库，包含 Flask 后端、Vue 管理前端，以及用于远程访问的独立 CLI/SDK 包。

**[English](README.md)** | **[中文](README.zh-CN.md)**

## 仓库包含内容

- `intent-hub-backend/`：后端服务包
- `intent-hub-frontend/`：管理控制台
- `intent-hub-cli/`：独立分发的 CLI 和 Python SDK
- `docs/`：项目共享文档

当前后端主要暴露三层接口：

- 租户运行时接口：`/v1/me`、`/v1/route`、`/v1/dispatch`
- 租户控制面接口：`/tenant/*`
- 平台管理员接口：`/admin/*`

旧单租户接口如 `/routes`、`/settings`、`/diagnostics/*`、`/reindex`、`/predict` 仍保留兼容能力，但当前项目文档以多租户 API 为主。

## 快速开始

对于普通用户，直接访问线上服务：

- Web 入口：`http://intenthub.free4inno.com/`

如果你需要远程 CLI 或 Python SDK，请安装：

```bash
pip install intent-hub-cli==0.1.4
```

面向终端用户的 skill 扫描已经改为客户端本地目录模式：

1. CLI 和 Python SDK 扫描用户机器上的绝对路径或相对路径，收集 `SKILL.md` 后上传到后端。
2. Web 租户页通过浏览器目录选择器读取用户本地目录中的 `SKILL.md` 并上传。
3. 后端不再假设普通租户可以直接指定部署机器上的目录做日常扫描。

## 本地开发

### 后端

```bash
cd intent-hub-backend
pip install -e .[dev]
python run.py
```

### 前端

```bash
cd intent-hub-frontend
npm install
npm run dev
```

### 独立 CLI 包

如果你只需要调用远程 Intent Hub 服务，请安装独立包：

```bash
pip install intent-hub-cli==0.1.4
```

CLI 扫描示例：

```bash
intent-hub skills scan --source-path ./skills
intent-hub skills scan --source-path D:/skills --source-label team-skills
intent-hub route --dispatch "帮我整理 wiki"
intent-hub sync --route-ids 12,15 --json
```

## 运行时数据布局

后端运行时数据位于 `intent-hub-backend/data/`。

关键路径：

- `platform/tenants.json`：租户元数据与 access code 记录
- `platform/admin_settings.json`：平台管理员设置
- `tenants/<tenant_id>/routes.json`：租户路由
- `tenants/<tenant_id>/settings.json`：租户配置
- `tenants/<tenant_id>/diagnostics_cache.json`：诊断缓存
- `tenants/<tenant_id>/skills_index.json`：skills 扫描索引
- `tenants/<tenant_id>/imports/`：导入草稿

旧的单租户文件如 `routes.json`、`settings.json` 可能仍存在于仓库中用于兼容或迁移，但当前事实上的数据来源是租户目录。

## 主要文档

- `USER_GUIDE.md`：面向使用者的操作说明
- `docs/API.md`：接口与鉴权说明
- `docs/ARCHITECTURE.md`：架构、目录与兼容层说明
- `intent-hub-cli/README.md`：CLI/SDK 包使用说明
- `intent-hub-cli/PUBLISH.md`：独立包发布流程

## 目录结构

```text
intent-hub/
├── docs/
├── intent-hub-backend/
│   ├── intent_hub/
│   ├── data/
│   └── tests/
├── intent-hub-cli/
│   ├── intent_hub_cli/
│   └── tests/
├── intent-hub-frontend/
│   ├── public/
│   └── src/
├── AGENT.md
├── README.md
├── README.zh-CN.md
└── USER_GUIDE.md
```

## 许可证

MIT，详见 `LICENSE`。
