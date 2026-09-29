# 多上游独立拉取

## 已确认的需求

2026-09-28 用户确认：设置支持多个同协议上游；按上游名称和原始 ID 用点号连接生成路由标识；现有配置转为默认上游。名称唯一、不含点号，首次成功拉取后锁定。支持单独手动拉取，保留人工覆盖和本地记录 ID。

## 行为与实现约定

- `UPSTREAMS` 保存稳定内部 ID、名称、URL、标签 ID。旧单上游配置兼容为名称 `default` 的默认上游。
- 名称采用现有路由的小写约定，不能包含空白或点号。原始 ID 中可能被路由标准化改变的字符使用可逆编码，普通数字 ID 直接保留。
- 每个拉取任务固定自己的上游配置快照；该上游在执行期间被修改或移除时，不提交旧数据。其他上游设置变更不影响该任务。
- 路由匹配必须同时满足所属上游与原始 ID；禁止接管手工路由或其他上游数据。重复 ID、身份冲突整批回滚。
- 默认上游存量记录在本地仓库初始化时迁移；保留来源快照、人工覆盖、本地 ID 和关联记录，递增同步版本并通过 outbox 更新索引。冲突时不做部分迁移。
- 成功完整拉取后锁定名称，包括有效空列表；部分拉取写入了数据也锁定，防止已存在路由身份改变。移除配置保留数据、名称保留记录，避免另一上游接管。
- 上游返回空列表或不完整列表沿用现有保护，不批量禁用本地数据；完整非空拉取仅判断该上游缺失。
- 未指定上游的旧拉取接口继续拉取默认上游，不表示全部拉取。默认上游被移除后明确报错。

## 接口与兼容

所有上游必须遵循同一套 [上游 Agent 拉取 API 协议 v1](../../api/upstream-agent-protocol.md)。设置中的 URL 是公共前缀，固定拼接 `/resource/search` 和 `/resource/{id}/detail`；请求参数、分页和资源字段见协议文档。

`GET /settings` 返回 `UPSTREAMS`，每项包含 `id/name/url/label_ids`，以及只读 `name_locked/last_result`。`POST /settings` 可只提交 `UPSTREAMS` 数组；空数组代表移除全部上游配置，不删除路由。旧 `AGENT_API_URL/AGENT_API_LABEL_IDS` 写入仍映射到默认上游。

`POST /routes/upstream-pull` 接受 `{"upstream_id":"..."}`，返回 HTTP 202 任务。`GET /sync-tasks` 中的 `source_config.SOURCE_INSTANCE` 区分上游。仍复用单 worker 队列：可以分别提交、分别失败和重试，独立拉取不意味着并行访问上游。默认上游的内部 ID 沿用 `SOURCE_INSTANCE`，初始名称为 `default`；其余 ID 由界面生成并随配置持久化。

设置页的上游配置单独保存；未保存的修改禁止拉取。列表页旧按钮明确标为“拉取默认上游”。拉取后名称由前后端共同锁定，上游路由标识禁止在普通编辑表单中修改。配置删除后的历史名称仍被保留，重新连接应复用原内部 ID，不允许新 ID 接管历史名称。

## 实现入口

- [配置、身份与迁移](../../../intent-hub-backend/intent_hub/upstreams.py)、[设置配置](../../../intent-hub-backend/intent_hub/config.py)
- [拉取与数据合并](../../../intent-hub-backend/intent_hub/services/upstream_agent_service.py)、[持久任务队列](../../../intent-hub-backend/intent_hub/services/sync_task_service.py)
- [设置页上游组件](../../../intent-hub-frontend/src/components/UpstreamSettings.vue)
- [多上游回归测试](../../../intent-hub-backend/tests/test_multiple_upstreams.py)

## 验证与交付状态

2026-09-28，Windows / PowerShell，本地修改已完成，未提交或部署。

| 验证 | 实际结果 |
| --- | --- |
| `python -m pytest intent-hub-backend/tests -q --tb=short` | **229 passed**；38 条既有 Pydantic 弃用警告。见 [完整输出](evidence/backend-tests.txt) |
| `npm run build`（前端目录） | `vue-tsc -b` 和 Vite 构建通过；存在 bundle 大小警告。见 [构建摘要](evidence/frontend-build.md) |
| 浏览器真实表单操作 | 新增 partner、编辑默认上游 URL、单独保存、分别拉取、重复拉取、刷新页面后名称锁定均通过 |
| 隔离与身份 | 本地同协议 HTTP fixture 均返回 ID 123，实际保存为 `default.123` 和 `partner.123`；重复拉取新增 0、未变 1。见 [脱敏结果](evidence/ui-results.json) |
| 实际渲染 | 检查了 [桌面 1280px](evidence/settings-desktop.png) 和 [手机 390px](evidence/settings-mobile.png)；上游表单换行正常，浏览器无 JavaScript 错误 |
| 差异检查 | `git diff --check` 通过；保留原有 settings.json 修改及其他未跟踪文件 |

浏览器验收使用隔离 SQLite、配置目录及本地 HTTP fixture，未连接真实上游。为隔离外部依赖，浏览器场景中的向量同步使用测试替身，因此截图的“索引已同步”仅证明任务状态展示，不能作为真实 Qdrant/Embedding 服务验收；索引相关逻辑由现有后端回归覆盖。

启用新版时，本地仓库初始化会自动迁移默认上游的旧标识，并入队更新索引；旧标识不保留别名。迁移事务发生冲突或缺少来源 ID 时整批回滚并报错，应修正冲突记录后再启动，不删除原记录来绕过校验。需要回退数据时使用启用前完整 SQLite 备份；仅回退代码不会恢复旧路由标识。实现交付时尚未重启运行环境，后续启动状态见下文。

### 本地启动验证（2026-09-28）

用户随后要求本地启动服务。确认旧后端没有活动任务后，备份 SQLite 与设置至本地 `.runlogs/backups/multiple-upstreams-20260928-155537/`，再以 `python -u run.py` 隐藏启动新版后端，复用 5173 端口的 Vite 前端。

- `/health`、`/health/ready`、管理员登录、前端页面和经前端代理访问设置接口均返回 200；就绪状态为 `ready`。
- 现有 8 条上游记录已迁移为 `default.ID`，默认上游名称已锁定。逐记录对照备份，确认本地 ID、名称、描述、语料、负例、阈值、来源快照、详情、生命周期和人工覆盖均保留。
- 8 条记录的同步状态均为 `synced`，`version == synced_version`；检查时活动任务为空。
- 本轮未主动拉取真实上游，也未执行新的预测效果测试；以上证明本地启动、迁移和后台同步状态，不代表真实上游联调或生产部署完成。备份包含私有配置，只留在本地运行目录，不作为公开交付附件。
