# AGENT.md

本文件用于说明在 `intent-hub` 仓库内执行任务时的统一操作约定。

## 1. 命令执行规则

- 统一使用项目约定的命令与工具执行开发、测试、构建任务。

## 2. 仓库结构

- 后端：`intent-hub-backend/`
- 前端：`intent-hub-frontend/`
- 后端文档：`intent-hub-backend/docs/`

## 3. 常用验证命令

- 后端测试：`pytest intent-hub-backend/tests -q`
- 前端构建：`npm run build`（在仓库根目录执行）

## 4. 文档约定

- 多租户与操作说明优先维护在：`intent-hub-backend/docs/USER_GUIDE.md`
- 设计与里程碑文档放在：`intent-hub-backend/docs/`

## 5. 优先级

- 用户最新明确指令优先于本文件。
- 若与系统/开发者上层指令冲突，遵循上层指令。
