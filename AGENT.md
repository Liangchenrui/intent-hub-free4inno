# AGENT.md

本文件定义 `intent-hub` 仓库内的统一协作约定。

## 仓库事实

- 根目录是主入口，公共文档统一维护在 `docs/`。
- 后端位于 `intent-hub-backend/`，提供 Flask API、兼容单租户接口、多租户管理接口和运行时接口。
- 前端位于 `intent-hub-frontend/`，提供 Vue 3 + Vite 管理台。
- 远程 CLI 与 Python SDK 位于 `intent-hub-cli/`，作为独立分发包维护。

## 文档约定

- 根目录文档优先级最高：
  - `README.md` / `README.zh-CN.md`：项目概览与快速开始
  - `USER_GUIDE.md`：面向使用者的操作说明
  - `docs/API.md`：接口说明
  - `docs/ARCHITECTURE.md`：架构与数据布局
- 如子项目需要独立分发或发布说明，可在子项目内保留局部文档，例如 `intent-hub-cli/README.md`、`intent-hub-cli/PUBLISH.md`。

## 常用验证命令

- 后端测试：`pytest intent-hub-backend/tests -q`
- CLI 测试：`pytest intent-hub-cli/tests -q`
- 前端构建：在 `intent-hub-frontend/` 下执行 `npm run build`

## 清理规则

- 可再生产物、缓存和临时目录不应作为有效源码或文档的一部分保留。
- 包括但不限于：`.venv/`、`node_modules/`、`dist/`、`*.egg-info/`、`__pycache__/`、测试 `.tmp/`。
- 示例数据与运行时数据是否保留，应以是否影响当前本地运行和调试为准。

## 优先级

- 用户当前指令高于本文件。
- 若与更高层系统或开发约束冲突，遵循更高层约束。
