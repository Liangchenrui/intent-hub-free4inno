# 上游快速拉取与差量同步

## 目标与契约（2026-09-19，实施前记录）

用户确认上游没有变更游标或版本，要求快速、简洁。采用全量获取、内存比较、差量保存、后台增量索引；不改上游协议、不部署、不修改本地密钥。

- Master 拉取接口返回 202 和持久任务；同一来源配置的活动拉取合并。BUPT 保留同步拉取响应。
- 初始设计希望路由字段齐全即可使用列表；实测发现列表缺少详情专有字段，因此最终只在列表含完整详情契约时跳过详情。其余获取详情：8 条以内复用连接串行，更多条目最多 8 路并发；线程独立 Session 共用连接池。
- 失败详情保留原记录；不完整列表不能据此停用记录。已实测验证 pageNum/pageSize，按 total 补齐分页；页码、总数异常或重复记录时停止并标记不完整。未知分页格式不猜测。
- 以 route_key 为唯一身份，不论来源类型或来源 ID；相同标识更新同一记录，不追加后缀。规范化字段比较；只保存变化行。保留字段覆盖，details 继续归上游管理。
- 拉取后在事务内重新读取当前记录并合成，业务变化与 outbox 一起提交；仅基线变化不入队。拉取时间写来源级记录。
- 沿用缺失停用及人工生命周期覆盖规则；空列表仍保守保留本地数据并提示。
- 索引比较排除来源基线和拉取时间；整体摘要仅写元数据点，避免描述变化连带刷新所有语料点。
- 拉取、对照及索引期间使用按钮 loading；完成、部分成功或失败通过顶部消息通知，结果统计随通知展示，不保留页面状态块。页面重新打开不弹出历史完成消息；失败保留重试入口。本地完成不等于索引成功。

## 顺序与验收

1. 改来源抓取和事务差量保存：无变化零 Agent 写入、零新 outbox；覆盖字段变化只保存基线；并发编辑不丢失。
2. 接入已有持久任务与页面：202、重复提交合并、失败可重试、重启任务恢复、旧配置任务不误执行。
3. 收紧向量写入：单条描述至多一个新编码文本且不改语料点；语料增删复用未变向量。
4. 后端回归、前端构建、OpenAPI 检查及浏览器实际渲染；保存必要证据。

## 实现入口

- [AgentSource](../../../intent-hub-backend/intent_hub/agent_source.py)：分页、完整详情检测、连接池、并发上限、失败隔离及请求计数。
- [UpstreamAgentService](../../../intent-hub-backend/intent_hub/services/upstream_agent_service.py)：事务内新鲜读取、字段覆盖、差量保存、来源范围及缺失判断。
- [SyncTaskService](../../../intent-hub-backend/intent_hub/services/sync_task_service.py)：持久拉取任务、去重、阶段状态、索引任务关联和中断恢复。
- [delta_sync](../../../intent-hub-backend/intent_hub/services/delta_sync.py)：管理元数据不触发索引写入，整体哈希不再扩散到语料点。
- [AgentList](../../../intent-hub-frontend/src/views/AgentList.vue)：复用任务轮询，显示结果和索引失败重试；[API 契约](../../API.md)。
- [上游回归测试](../../../intent-hub-backend/tests/test_upstream_agents.py)、[索引回归测试](../../../intent-hub-backend/tests/test_delta_sync.py)。

## 实测调整与限制

2026-09-19 只读 GET 验证了现有上游列表：返回 records/total/pageNum/pageSize，pageNum/pageSize 可以分页。列表资源包含路由字段，但详情另含 attachments、author、labelsByCategory、parameters、source，不能用列表资源直接替换完整 details。因此当前上游仍需获取全部详情，无可靠版本信息不承诺只请求变化项。

对当前 8 个 Agent（3 次标签列表请求 + 8 次详情请求）重复只读测量，单连接样本约 592–694 ms；4/8 路并发样本约 1254–1684 ms。小批量并发连接建立的成本高，最终默认 <=8 条使用串行共享连接池，更多条目最多 8 路并发。最终默认单次样本 623.766 ms。以上不是严格对照实验，也不是 p50/p95 或 SLA。

真实上游内容在隔离临时 SQLite 中首次创建 8 条，再次拉取 8 条均未变化：Agent 写入 0，outbox 新增 0。没有向用户数据库、上游、真实 Qdrant 写入；没有调用真实 Embedding。脱敏计数和完整测量序列见 [只读证据](evidence/live-read-only.json)。

SQLite 是管理状态和 raw details 的权威来源。Qdrant 恢复元数据只随有效索引变化刷新，不能作为最新人工覆盖、来源基线或 details 的完整备份；该取舍避免基线变化重新写索引。

## 验证与交付状态

- 最终相关回归：42 passed（38.85 s）；覆盖无变化零写入、覆盖保留、网络期间人工修改、分页、失败隔离、标签范围变化、202 去重、任务重启、描述单文本编码、语料点不被连带修改、旧哈希兼容。
- 前端 `npm run build` 通过；保留既有大 chunk 体积警告。
- 后端目录 `python -m intent_hub.openapi --check` 通过；OpenAPI 已更新为 202 契约。
- 最终全量后端回归：191 passed，8 个既有 Pydantic 弃用警告，113.44 s。验证摘要见 [验收证据](evidence/validation.json)。
- 浏览器控制初始化返回 `nodeRepl.fetch request failed`，未获得可用浏览器，因此界面实际渲染与点击验收未完成；构建通过不代替该项。
- 未重启现有服务、未提交/推送、未部署。启用需要后端加载新代码及前端更新；保留原有数据库和工作区修改。

复现命令（仓库根目录）：

```powershell
python -m pytest intent-hub-backend/tests -q --basetemp=.tmp/pytest-upstream-delivery --durations=5
```

前端目录执行 `npm run build`；后端目录执行 `python -m intent_hub.openapi --check`。真实网络测量仅记录上述来源和负载，不应把一次测量外推为大规模性能结论。


路由标识身份修正：上游优先使用 `route_key` / `routeKey`；当前上游未提供此字段时沿用规范化 title 生成标识。不同标识视为不同实体，来源 ID 仅用于追踪。一次拉取出现重复标识时整批报错，不按顺序覆盖。已有历史后缀标识与 `demo.1` 等自定义标识不会自动改名或合并。

身份规则修正验证：45 项相关测试通过（40.76 s，2 个既有弃用警告）。当前 16 条数据副本与真实上游隔离对照新增 0、有效更新 7、未变化 1、缺失 7，结果见 [标识对照证据](evidence/route-key-replay.json)。后缀标识作为不同实体按缺失处理，不自动合并/删除。已保留原进程环境重启本地后端，健康接口返回成功；未在真实数据库执行拉取或数据归并。
