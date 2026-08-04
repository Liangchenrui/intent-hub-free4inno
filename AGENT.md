# AGENT.md

本文件定义 `intent-hub` 仓库内的统一协作约定。

## 仓库事实

- 根目录是主入口，公共文档统一维护在 `docs/`。
- 后端位于 `intent-hub-backend/`，提供单工作区 Flask 管理与路由接口。
- 前端位于 `intent-hub-frontend/`，提供 Vue 3 + Vite 管理台。

## 文档约定

- 根目录文档优先级最高：
  - `README.md` / `README.zh-CN.md`：项目概览与快速开始
  - `USER_GUIDE.md`：面向使用者的操作说明
  - `docs/API.md`：接口说明
  - `docs/ARCHITECTURE.md`：架构与数据布局

## 常用验证命令

- 后端测试：`pytest intent-hub-backend/tests -q`
- API 文档一致性：`python -m scripts.api_docs check`
- 前端构建：在 `intent-hub-frontend/` 下执行 `npm run build`

## 清理规则

- 可再生产物、缓存和临时目录不应作为有效源码或文档的一部分保留。
- 包括但不限于：`.venv/`、`node_modules/`、`dist/`、`*.egg-info/`、`__pycache__/`、测试 `.tmp/`。
- 示例数据与运行时数据是否保留，应以是否影响当前本地运行和调试为准。

## 优先级

- 用户当前指令高于本文件。
- 若与更高层系统或开发约束冲突，遵循更高层约束。
