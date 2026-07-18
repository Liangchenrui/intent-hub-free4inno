# 使用说明

1. 使用用户名和密码登录，获得 30 分钟有效的 Bearer API Key。
2. 在 Agent 页面点击“同步 Agent”。同步会读取上游全部资源详情，并按 `extent00` 正向语料和 `extent01` 负向语料重建当前 Collection。
3. 在路由测试页输入问题。最高分达到 `0.8` 时返回 Agent 完整详情及分数，否则返回 `data/default_route.txt` 的文本。
4. 设置页只允许修改 Qdrant Collection 名称。修改后需重新同步。

Agent 页面和接口均不提供新增、修改或删除能力。

