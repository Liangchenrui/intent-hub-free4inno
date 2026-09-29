# Intent Hub 路由 API

版本：0.4.0 · 更新日期：2026-09-29

输入用户需求，返回匹配的 Agent。本文统一使用 `POST /route`，请求与响应均为 JSON。

[OpenAPI 文件](routing-api.openapi.yaml)可导入接口调试工具。以下地址、密钥和标识均为示例，需替换为实际部署值。

## 请求

```http
POST /route
Authorization: Bearer <ROUTE_API_KEY>
Content-Type: application/json
```

```json
{
  "query": "查询订单物流",
  "collection": "intent_hub",
  "upstream_id": "orders-platform"
}
```

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `query` | string | 是 | 用户需求，不能是空字符串或纯空白 |
| `collection` | string | 否 | 指定现有 Collection，最长 255 字符；省略或 null 使用服务默认库 |
| `upstream_id` | string | 否 | 上游配置的稳定 `id`，对应 `source.instance`；省略或 null 不限来源 |
| `learn_from_fallback` | boolean | 否 | 默认 true；兜底命中后自动积累语料，测试时可设 false |

两个筛选参数同时传入时取交集，正例检索、负例检查和 LLM 兜底均遵守该范围。筛选值会去除首尾空白，空白值返回 400。未知字段和错误类型也返回 400，避免拼错筛选参数后意外查询全部来源。

`upstream_id` 区分大小写，不是上游名称、URL 或 Agent 原始 ID。例如上游配置为 `{"id":"orders-platform","name":"orders"}`，应传 `orders-platform`。

鉴权也支持 `X-API-Key`。优先使用服务配置的 `ROUTE_API_KEY`，未配置时沿用 `AUTH_CODE`；无有效密钥返回 401。管理认证启用时也接受有效登录会话，供管理台测试使用。经前端代理调用时，路径为 `/api/route`。

## 响应

命中示例：

```json
{
  "success": true,
  "data": {
    "matched": true,
    "agents": [
      {"id": 1, "name": "订单物流查询", "route_key": "orders.71", "agent": {"id": 71, "title": "订单物流查询"}, "score": 0.93}
    ],
    "text": null,
    "match_source": "semantic",
    "fallback_status": null
  },
  "error": null
}
```

| 字段 | 说明 |
| --- | --- |
| `success` | 请求是否处理成功；不代表命中 |
| `data.matched` | 是否匹配到 Agent |
| `data.agents` | 匹配列表；语义命中按分数降序排列，可能有多个结果 |
| `data.agents[].id / name / route_key` | 本地路由 ID、名称和稳定业务标识；用于后续处理和反馈 |
| `data.agents[].agent` | Agent 的原始详情，字段由来源决定，也可能为空对象 |
| `data.agents[].score` | 向量相似度，不是概率；LLM 兜底命中时为 null |
| `data.text` | 未命中时的默认提示，由部署配置决定；命中时为 null |
| `data.match_source` | `semantic`：语义命中；`llm_fallback`：LLM 兜底命中；`default`：未命中 |
| `data.fallback_status` | 兜底状态，见下表；未使用或未启用兜底时为 null |

| 兜底状态 | 含义 |
| --- | --- |
| `matched` | 已选择一个候选 Agent |
| `no_match` | 候选均不适用 |
| `ambiguous` | 存在歧义，可提示用户补充信息 |
| `no_candidates` | 没有有效候选 |
| `unavailable` | 兜底服务或结果不可用 |

未命中也返回 HTTP 200，此时 `success=true`、`matched=false`、`agents=[]`、`match_source="default"`。未知上游或筛选范围内无候选按未命中处理，不会改查其他来源或 Collection。

## 错误

```json
{
  "success": false,
  "data": null,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "请求参数错误",
    "detail": "collection 'missing' 不存在"
  }
}
```

| HTTP 状态 | 错误码 | 含义 |
| --- | --- | --- |
| 400 | `INVALID_REQUEST` | 参数错误或指定 Collection 不存在 |
| 401 | `UNAUTHORIZED` | 缺少或无效密钥 |
| 503 | `SERVICE_NOT_READY` | 路由组件尚未就绪 |
| 500 | `INTERNAL_ERROR` | 服务运行异常 |

LLM 兜底不可用可以返回 HTTP 200，并通过 `default/unavailable` 表达；调用方应同时检查 HTTP 状态与业务字段。

## 使用边界

- Collection 选择只影响本次请求，不创建库、不改变全局配置。
- 指定库须兼容当前 embedding 模型、维度及本地路由目录；不能直接作为独立的外部 Agent 目录使用。
- 只有启用的路由可以命中；语义分数需达到该路由阈值，命中其负例时会被排除。
- 默认库在 `learn_from_fallback=true` 时启用兜底自动学习；查询非默认库时关闭自动学习，避免写回默认库。
- 本文描述当前工作区接口设计，不代表线上部署已更新。

## PowerShell 示例

```powershell
$body = @{
    query = '查询订单物流'
    collection = 'intent_hub'
    upstream_id = 'orders-platform'
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri 'http://localhost:8000/route' `
    -Headers @{ Authorization = "Bearer $env:INTENT_HUB_ROUTE_KEY" } `
    -ContentType 'application/json; charset=utf-8' `
    -Body ([System.Text.Encoding]::UTF8.GetBytes($body))
```

`INTENT_HUB_ROUTE_KEY` 是示例客户端的环境变量，请填入实际路由密钥。

## 旧调用迁移

旧 `/predict`、`/compat/master/predict`、`/compat/bupt/route` 已移除，调用返回 404。统一改为 `/route`，将请求字段 `text` 改为 `query`，从 `data.agents` 读取结果。此前已有 `/route` 调用仍使用原响应结构，并新增稳定的路由标识字段。管理接口的兼容入口不受本次调整影响。
