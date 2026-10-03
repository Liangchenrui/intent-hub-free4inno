# 兜底成功后自动积累语料

> 2026-09-30 更新：上游拉取不再导入正、负例句，完整保留本地语料与自动学习记录；恢复上游字段仅支持名称和描述。下文涉及“合并上游语料”的内容保留为历史行为。当前实现见[同步与管理员处理闭环](../2026-09-30-fusion-agent-requirements.md)。

2026-09-28：用户确认请求原文入库、后台索引更新、上游合并保留方案。

同日调整：测试界面仅通过已有点赞/点踩收集反馈，不自动学习。`/predict` 新增严格布尔字段 `learn_from_fallback`（默认 `true`）；测试界面显式传 `false`。外部 API 省略该字段继续自动学习，BUPT 路由 API 保持自动学习。

调整后验证：`python -m pytest intent-hub-backend/tests/test_llm_fallback.py intent-hub-backend/tests/test_prediction_service.py intent-hub-backend/tests/test_predict_api.py -q`：58 passed（88.71s）。新增 HTTP 回归覆盖无检索结果/低于阈值两个入口，以及关闭、开启、省略开关三种请求；关闭时实体内容和同步状态不变，仍正常返回兜底结果。前端 `npm run build` 通过，保留既有大 bundle 提示。本地开发后端已重启加载该调整；未发布到远程环境。

## 行为与设计

- 仅 `llm_fallback / matched` 后，将去除首尾空白的请求追加到对应 Agent 的 `utterances`。普通命中、默认路由、无匹配、歧义及异常不学习。
- SQLite 事务内重新检查实体状态与内容、去重、更新版本并保存 outbox。并发相同请求最多新增一条；实体职责变更时跳过学习。
- `fallback_utterances` 保存自动添加文本及 UTC 时间，通过路由和 Agent 读取接口可查看。编辑语料删除文本时一并清除其来源记录。
- 上游拉取或恢复上游语料字段时，合并上游语料与自动积累语料，不把自动学习标为整字段人工覆盖。
- 入库后提交现有后台同步队列，不等待向量化。入库失败不改变路由返回；调度失败保留 outbox，可在队列重启时恢复；后台任务沿用现有重试机制。
- 直接采用兜底判断，模型误判可能影响后续检索；可通过已有语料编辑接口删除误加内容。删除后若未来再次兜底匹配，仍可能重新学习。

## 实现与验收

入口为 `fallback_service.py`、`fallback_learning.py`，持久化及来源兼容在 `repository.py`，上游合并在 `upstream_agent_service.py`。数据结构向后兼容，旧记录的来源字典默认为空，无需迁移。

## 验证结果与运行状态

2026-09-28 在 Windows / Python 本地环境执行，仓库根目录设置 `PYTHONPATH=intent-hub-backend`：

```powershell
python -m pytest intent-hub-backend/tests/test_llm_fallback.py intent-hub-backend/tests/test_upstream_agents.py -q
# 70 passed, 1 warning in 80.16s
python -m pytest intent-hub-backend/tests/test_route_service.py intent-hub-backend/tests/test_route_manager.py intent-hub-backend/tests/test_unification.py intent-hub-backend/tests/test_core_components.py intent-hub-backend/tests/test_async_sync.py intent-hub-backend/tests/test_prediction_service.py -q
# 40 passed, 2 warnings in 51.86s
python -m intent_hub.openapi --check --output docs/intent-hub-openapi.json
```

- 新增测试使用临时 SQLite、内存 Qdrant 和模拟模型/编码器：验证首次兜底入库，处理后台队列后再次请求走 semantic；16 个并发相同请求仅新增一次；无匹配/歧义不写入；数据库失败仍返回匹配；调度失败保留 outbox 并可恢复。
- 上游测试验证新上游语料与本地自动语料合并、上游快照保持原始内容、重复拉取不升版本、恢复字段保留自动语料、旧客户端省略来源字段仍保留来源、手动删除后不被拉取复活。
- 原有兜底异常、禁用、负例排除、实体变更、管理契约和队列回归均通过。警告来自既有鉴权代码的 Pydantic `dict()` 弃用提示。
- OpenAPI 重新生成时一并补齐已有模型中的 `display_order` 字段；无对应业务逻辑变更。
- 未验证真实模型准确率或线上延迟，未远程部署；Git 交付状态见[收尾记录](../2026-09-28-closeout.md)。已有本地设置和研究文件保持原状。

随现有大模型兜底启用状态生效，无新增开关。索引异步更新期间仍可能继续进入兜底或因旧索引 hash 失效返回默认路由；自动语料是否提升真实检索质量需线上数据验证。
