# 五分钟 Self-Healing 演示数据与修复手册

## 演示起点

- Collection：`IJCAI`
- Agent：`OrderTracking`、`DeliveryDelay`
- 每个 Agent：12 条正例、2 条基础负例
- 实例冲突：4 组
- 区域相似度：约 `0.865`
- 固定测试语料：`My tracking has not updated in two days.`

测试时两个 Agent 都会进入候选列表，`OrderTracking` 以很小的分差成为 Best Match；按照业务边界，这条带有“两天没有更新”异常证据的语料应属于 `DeliveryDelay`，因此可以明确展示错误路由。

## 两种冲突类型

1. 区域重叠：两个 Agent 的整体正例点云过于接近，演示数据约为 `86.5%`。
2. 实例冲突：具体正例对的相似度超过实例阈值。

当前 4 组实例冲突：

| OrderTracking | DeliveryDelay | 预计相似度 | 演示操作 |
|---|---|---:|---|
| `My tracking has not updated in two days.` | 同一句 | 约 100% | 在 OrderTracking 中设为负例 |
| `The delivery appears to be delayed.` | `It appears that my delivery is delayed.` | 约 95% | 从 OrderTracking 拖到 DeliveryDelay |
| `Could my package be stuck at the sorting hub?` | `My package appears stuck at the sorting hub.` | 约 95% | 从 OrderTracking 删除 |
| `Is my delivery still on schedule?` | `Has my delivery fallen behind schedule?` | 约 92% | 在 UMAP 点位上改写 |

## 现场修复动作

打开 `OrderTracking` 与 `DeliveryDelay` 的冲突详情后：

1. 点击 UMAP 中的 `Is my delivery still on schedule?`，改为 `Where was my parcel last scanned?`。
2. 在对比池中将 `What is the current shipping status?` 改为 `Show the current carrier status for my tracking number.`。
3. 删除 `Could my package be stuck at the sorting hub?`。
4. 将 `My tracking has not updated in two days.` 从 `OrderTracking` 设为负例。
5. 将 `The delivery appears to be delayed.` 从左侧拖到 `DeliveryDelay`。
6. 点击“获取修复建议”，展示 LLM 给出的新正例、负例和修复理由；以人工操作为主，不必全选应用建议。
7. 点击“同步并重新检测”。系统保存两侧语料、增量同步向量索引并重新诊断。

这套修复结果在旧演示数据上已实际验算，刷新诊断后返回 0 个冲突。

## 修复后测试与反馈

再次输入：`My tracking has not updated in two days.`

由于它已经成为 `OrderTracking` 的负例，同时仍是 `DeliveryDelay` 的正例，`OrderTracking` 会被负例机制排除，Best Match 应变为 `DeliveryDelay`。

点击 `DeliveryDelay` 结果上的点赞，将这条成功样本加入该 Agent 的正例。完整闭环为：

`管理 → 测试发现错误 → 诊断定位 → UMAP/对比池修复 → 自动同步与复检 → 测试验证 → 点赞反馈`

## 当前版本注意事项

当前代码版本已改为从上游 API 只读 Agent，不再使用旧版 `routes.json` 和 `diagnostics_cache.json` 本地数据文件。正式演示前，需要通过当前上游数据源或 Collection 导入流程准备上述两个 Agent 和四组冲突，不要重新引入旧的本地 Agent 写路径。

第一次进入 Map 时可能需要计算 UMAP，建议演示前预热一次。LLM 建议受网络延迟影响，五分钟演示中建议最多等待 30 秒。
