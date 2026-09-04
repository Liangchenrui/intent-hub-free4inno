# Intent Hub 五分钟演示讲稿（中英文）

## 中文版

### 0:00–0:25｜开场

大家好，Intent Hub 是一个具备 self-healing 能力的 semantic agent router。它不仅把用户请求路由到合适的 Agent，还通过测试、冲突诊断、人工与 LLM 协同修复、自动同步和反馈学习，持续维护 Agent 之间的语义边界。

### 0:25–1:05｜Agent 管理

这里是当前 Collection `IJCAI` 的意图实体列表。我们有两个相邻 Agent：`OrderTracking` 处理正常的包裹位置、物流扫描和预计送达时间；`DeliveryDelay` 处理延迟、超期、停滞和长时间没有更新等异常。

我点击编辑 `OrderTracking`。这里的正向例句定义“什么应该路由到这个 Agent”，负向例句定义“什么看起来相似、但不应该路由到这里”。除此之外，每个 Agent 还有职责描述、稳定的 route key 和匹配阈值。保存后，Intent Hub 会自动维护版本并同步向量索引。

### 1:05–1:35｜测试发现错误

现在进入测试，输入：`My tracking has not updated in two days.`。这句话包含“两天没有更新”的异常证据，业务上应该进入 `DeliveryDelay`。但当前 Best Match 是 `OrderTracking`，说明两个 Agent 的边界发生了冲突。我们记住这条语料，稍后用完全相同的输入做回归验证。

### 1:35–2:15｜诊断两类冲突

点击诊断。Intent Hub 展示两种冲突。第一种是区域重叠，也就是两个 Agent 的整体语义空间过于接近；演示数据的重叠约为 86.5%。第二种是实例冲突，也就是某一对具体语料高度相似。这里我们只预置四组，既能说明问题，也能在现场快速修完。

### 2:15–2:40｜Map

切换到 Map。UMAP 把高维向量投影到二维空间，每个点代表一条正向语料，颜色代表所属 Agent。两个点云交界处就是最容易误路由的区域。这个视图让我们不只看到一个分数，还能直观看到语料分布和边界是否健康。

### 2:40–4:15｜Self-Healing 修复

我点击修复 `OrderTracking`。上方是这两个 Agent 的局部 UMAP，下方是左右语料对比池。

先直接点击 UMAP 上的 `Is my delivery still on schedule?`，把它改成更明确的普通跟踪表达：`Where was my parcel last scanned?`。回到对比池，再把 `What is the current shipping status?` 改成更具体的 `Show the current carrier status for my tracking number.`，展示池内编辑。然后删除 `Could my package be stuck at the sorting hub?`。接着把测试中出错的 `My tracking has not updated in two days.` 从 `OrderTracking` 设为负例。最后，把 `The delivery appears to be delayed.` 直接拖到右侧的 `DeliveryDelay` 语料库。

这些操作分别展示了 UMAP 编辑、对比池编辑、删除、正例转负例和跨 Agent 拖拽。现在点击“获取修复建议”，LLM 会基于两个 Agent 的职责和冲突语料，给出新的判别性正例、负例和修复理由。LLM 提供建议，人工决定采用哪些内容，因此 self-healing 是可控、可审计的，而不是让模型无约束地改数据。

点击“同步并重新检测”。Intent Hub 会保存修改，增量同步向量库，并立即重新运行诊断。现在页面显示没有冲突，说明实例冲突和区域重叠都已经清除。

### 4:15–5:00｜验证与反馈闭环

最后回到测试，再次输入同一句：`My tracking has not updated in two days.`。现在它被正确路由到 `DeliveryDelay`。原因很清楚：它仍是 `DeliveryDelay` 的正例，同时已经成为 `OrderTracking` 的负例。

我点击正确结果上的点赞，把这次已验证的真实输入加入 `DeliveryDelay` 的正向语料。这样就完成了整个 self-healing 闭环：Agent 管理，测试发现错误，诊断定位冲突，在 UMAP 和对比池中修复，自动同步并复检，再通过点赞把成功反馈沉淀为新的训练证据。Intent Hub 管理的不只是一次路由，而是持续变得更健康的语义边界。

## English Version

### 0:00–0:25 | Introduction

Hello everyone. Intent Hub is a self-healing semantic agent router. It not only routes a user request to the right agent; it continuously maintains semantic boundaries through testing, conflict diagnostics, human-and-LLM-assisted repair, automatic index synchronization, and feedback learning.

### 0:25–1:05 | Agent Management

This is the intent entity list for the selected Collection, `IJCAI`. We have two neighboring agents. `OrderTracking` handles routine package location, carrier scans, and estimated delivery time. `DeliveryDelay` handles exceptions such as late or overdue parcels, shipments stuck in transit, and prolonged missing updates.

I will edit `OrderTracking`. Positive utterances define what should route to this agent. Negative utterances define what may look similar but must not route here. Each agent also has a responsibility description, a stable route key, and matching thresholds. After a save, Intent Hub versions the configuration and synchronizes the vector index automatically.

### 1:05–1:35 | Expose a Routing Error

Now I open Test and enter: `My tracking has not updated in two days.` The phrase “not updated in two days” is explicit exception evidence, so the correct agent is `DeliveryDelay`. However, the current Best Match is `OrderTracking`. This gives us a concrete boundary failure. We will reuse the exact same input after the repair.

### 1:35–2:15 | Diagnose Two Conflict Types

I open Diagnostics. Intent Hub reports two types of conflict. The first is region overlap: the overall semantic spaces of two agents are too close. In the demo data, the overlap is about 86.5 percent. The second is an instance conflict: a specific pair of utterances is highly similar. We intentionally prepared only four conflict pairs, enough to demonstrate the problem and still resolve it during a five-minute session.

### 2:15–2:40 | Map View

I switch to Map. UMAP projects high-dimensional vectors into two dimensions. Every point is a positive utterance, and each color represents an agent. The boundary between the two point clouds is where misrouting is most likely. This view makes semantic health visible instead of reducing it to a single score.

### 2:40–4:15 | Self-Healing Repair

I open Repair for `OrderTracking`. The local UMAP is at the top, and the two comparison pools are below it.

First, I click `Is my delivery still on schedule?` directly on the UMAP and rewrite it as the more specific routine-tracking example `Where was my parcel last scanned?`. Back in the comparison pool, I edit `What is the current shipping status?` into the more specific `Show the current carrier status for my tracking number.`. I then delete `Could my package be stuck at the sorting hub?`. Next, I convert our failed test utterance, `My tracking has not updated in two days.`, from a positive example into a negative example for `OrderTracking`. Finally, I drag `The delivery appears to be delayed.` into the `DeliveryDelay` pool.

These actions demonstrate direct UMAP editing, comparison-pool editing, deletion, positive-to-negative conversion, and cross-agent drag and drop. I now click “Get Repair Suggestions.” The LLM uses the responsibilities and conflict evidence to propose discriminative positive examples, negative examples, and a repair rationale. The LLM recommends; a human decides what to apply. That makes self-healing controlled and auditable rather than an unconstrained model rewrite.

I click “Synchronize and Redetect.” Intent Hub saves both pools, incrementally updates the vector index, and immediately reruns diagnostics. The page now reports no conflicts, confirming that both instance conflicts and region overlap have been removed.

### 4:15–5:00 | Validate and Close the Feedback Loop

Finally, I return to Test and enter the same sentence again: `My tracking has not updated in two days.` It now routes correctly to `DeliveryDelay`. The reason is explicit: it remains a positive example for `DeliveryDelay`, while it is now negative evidence for `OrderTracking`.

I click the thumbs-up button on the correct result, adding this validated real-world input to the positive examples of `DeliveryDelay`. This completes the self-healing loop: manage agents, expose an error through testing, diagnose the conflict, repair the boundary in UMAP and the comparison pools, synchronize and redetect automatically, validate with the same test, and convert successful feedback into new routing evidence. Intent Hub manages more than a single prediction; it keeps the semantic boundary healthy over time.
