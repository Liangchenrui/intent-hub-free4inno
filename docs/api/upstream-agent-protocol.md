# 上游 Agent 拉取 API 协议 v1

机器可读导出：[OpenAPI 3.0.3 YAML](upstream-agent.openapi.yaml)，可导入支持 OpenAPI 的接口工具。`servers.url` 是示例地址，接入时替换为实际公共前缀。

本文是 Intent Hub 上游接入的固定协议说明，依据 2026-09-30 的 [AgentSource](../../intent-hub-backend/intent_hub/agent_source.py) 与 [合并服务](../../intent-hub-backend/intent_hub/services/upstream_agent_service.py) 更新。新上游应按本文的标准格式提供接口。文档版本 `v1` 不表示 URL 中需要加入 `/v1`，当前没有协议版本协商机制。正、负例句由 Intent Hub 本地维护，上游语料字段不再解析或导入。

所有上游使用同一套路径、参数、响应包裹和字段映射。设置页仅配置名称、接口公共前缀和标签 ID，不支持自定义接口路径、字段映射或鉴权适配器。

## 1. 地址与调用方向

调用方向：**Intent Hub → 上游服务**。上游需要提供以下两个只读接口：

| 方法 | 相对于公共前缀的路径 | 用途 |
| --- | --- | --- |
| GET | `/resource/search` | 按标签分页列出 Agent |
| GET | `/resource/{id}/detail` | 取得指定 Agent 的详情 |

例如设置中的接口 URL 为 `https://agents.example.com/ac/api`，实际请求为：

```http
GET https://agents.example.com/ac/api/resource/search?labels=87
GET https://agents.example.com/ac/api/resource/123/detail
```

配置 URL 不能填写完整的 `/resource/search` 路径，也不能包含查询参数或片段。末尾 `/` 会被去除。多个上游可以使用不同域名、端口和公共前缀，但协议相同。

当前请求不主动附加 API Key、Bearer Token 或自定义认证头，也没有上游登录流程。Intent Hub 管理接口的登录凭据不会转发给上游。需要鉴权的上游需另行扩展适配能力，不能仅在现有设置中填写密钥。

## 2. 通用响应

成功请求应返回 HTTP 200、`Content-Type: application/json`，结构固定为：

```json
{
  "code": 200,
  "msg": "success",
  "data": {}
}
```

| 字段 | 标准类型 | 要求 |
| --- | --- | --- |
| `code` | integer | 成功时为数字 `200`，不能是字符串 `"200"` |
| `msg` | string | 可选；失败时提供可读原因 |
| `data` | object | 成功时必须是对象，列表也不能直接放在这里作为数组 |

失败示例：

```json
{
  "code": 404,
  "msg": "resource not found",
  "data": {}
}
```

HTTP 错误状态、非 JSON 内容、业务 `code` 非 200 或 `data` 非对象均会使该请求失败。当前每次 HTTP 请求的 `requests` 超时参数为 30 秒，不代表整次分页拉取必须在 30 秒内完成。

## 3. 资源列表

### 请求

```http
GET {base_url}/resource/search?labels=87
```

| 参数 | 类型 | 调用约定 |
| --- | --- | --- |
| `labels` | 数字 ID 的字符串形式 | 每次请求只传一个标签 ID |
| `pageNum` | integer | 从 1 开始；首次请求不传，上游必须默认返回第 1 页 |
| `pageSize` | integer | 正整数；首次请求不传，由上游选择默认页大小 |

配置 `label_ids` 为 `87,88,89` 时，Intent Hub 会分别查询三个标签，再按原始 ID 合并结果；不会把整个逗号串作为一次 `labels` 参数发送。同一 Agent 同时属于多个标签是合法情况，会去重后只取一次详情；重复记录内容应保持一致。

### 标准响应

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "records": [
      { "resource": { "id": 123 } },
      { "resource": { "id": 124 } }
    ],
    "total": 3,
    "pageNum": 1,
    "pageSize": 2
  }
}
```

| 字段 | 标准类型 | 语义 |
| --- | --- | --- |
| `records` | array | 当前页记录，空列表使用 `[]` |
| `records[].resource` | object | 资源对象，不能直接用资源对象替代外层记录包装 |
| `records[].resource.id` | integer 或非空 string | 上游范围内稳定且唯一的原始 ID |
| `total` | integer，≥ 0 | 当前标签筛选结果的总记录数，不是当前页数量 |
| `pageNum` | integer，≥ 1 | 当前页码 |
| `pageSize` | integer，≥ 1 | 当前分页大小 |

新上游应始终返回这些分页字段，即使只有一页。没有结果时返回 `records: []`、`total: 0`、`pageNum: 1` 和有效 `pageSize`。

### 分页行为与限制

上例中，Intent Hub 会继续请求：

```http
GET {base_url}/resource/search?labels=87&pageNum=2&pageSize=2
```

后续响应的 `total` 必须保持一致、`pageNum` 必须与请求一致，各页 ID 不能重叠。服务端应采用稳定顺序，避免拉取期间页面漂移。当前协议不支持游标分页，也不会根据 `next` 链接继续请求。

代码仅在首页满足 `total > 当前记录数`、`pageNum == 1` 且 `pageSize` 有值时自动翻页。翻页提前返回空页、重复 ID、变化的总数或错误页码，会把列表标记为不完整。首页的 `hasMore`、`has_more` 或 `next` 为真值也会触发不完整标记；新上游应使用上面的标准页码字段，不要依赖这些扩展字段。

兼容限制：旧响应省略 `total` 时，当前代码可能把已返回记录视为完整集合，无法发现被截断的数据。因此“代码能读取”不代表满足完整列表协议，新接入不能省略分页元数据。

## 4. 资源详情

### 请求与标准响应

```http
GET {base_url}/resource/123/detail
```

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "id": 123,
    "title": "天气查询",
    "text": "查询指定城市的天气和未来预报。",
    "extent00": ["北京今天天气怎么样", "明天上海会下雨吗"],
    "extent01": ["帮我订机票"],
    "attachments": [],
    "author": {},
    "labelsByCategory": {},
    "parameters": [],
    "source": {}
  }
}
```

| 字段 | 标准类型 | 必需 | 映射或用途 |
| --- | --- | --- | --- |
| `id` | integer 或非空 string | 是 | 原始 ID，字符串化后必须与列表 ID 相同 |
| `title` | string | 是 | 映射到路由 `name` |
| `text` | string | 是 | 映射到路由 `description` |
| `extent00` | 建议 array of string | 否 | 可选原始正例，仅保留在 `details`，不导入 `utterances` |
| `extent01` | 建议 array of string | 否 | 可选原始负例，仅保留在 `details`，不导入 `negative_samples` |
| `attachments` | 示例为 array | 否 | 附件原始信息，保存在 `details` |
| `author` | 示例为 object | 否 | 作者原始信息，保存在 `details` |
| `labelsByCategory` | 示例为 object | 否 | 分类标签原始信息，保存在 `details` |
| `parameters` | 示例为 array | 否 | 参数原始信息，保存在 `details` |
| `source` | 示例为 object | 否 | 上游自身的来源信息，保存在 `details`；不是 Intent Hub 的路由来源标识 |

后五个字段的内部结构当前没有固定解析约束，表中类型为接入示例，不是当前代码已实施的类型校验。完整资源对象及扩展字段会保存在路由 `details` 中。

`title`、`text` 会去除首尾空白。建议提供非空名称和清晰的能力描述；字段存在不等于路由质量合格。新建实体的本地正、负例句为空，描述仍可参与同步后的 Top-K 兜底检索。

`extent00` / `extent01` 缺失、为空或格式异常均不影响信息拉取；不执行语料解析，也不以语料变化触发提醒。原始详情字段沿用兼容返回，不表示已进入本地路由语料。详情缺少 `id` 时当前代码会沿用请求 ID，但标准响应仍应显式返回 `id`。

### 省略详情请求的条件

列表中的 `resource` 如果同时包含 `title`、`text`、`attachments`、`author`、`labelsByCategory`、`parameters`、`source` 这七个字段，Intent Hub 会直接使用该对象，不再请求详情。仅包含名称、描述仍会触发详情请求。上游应提供详情接口，以支持精简列表响应；不能假设每次同步都会访问详情接口。

## 5. 原始 ID 与路由身份

原始 ID 必须稳定，不能随着标题或描述变化，也不能在同一上游复用于另一实体。数值 `123` 与字符串 `"123"` 被视为同一 ID；`"00123"` 与 `123` 不同。推荐使用整数或仅包含 ASCII 字母、数字、下划线、短横线的字符串，确保可直接作为详情路径的单个段；当前适配器直接拼接详情路径，没有专门的 ID 路径编码步骤。

路由标识由 Intent Hub 生成：

```text
上游名称 = bupt，原始 ID = 123    → bupt.123
上游名称 = partner，原始 ID = 123 → partner.123
```

名称使用小写、唯一且不含点号或空白，拉取后锁定。普通数字 ID 原样连接；原始 ID 中不属于小写 ASCII 字母、数字、`_`、`-` 的字符，按 UTF-8 字节编码为小写 `%xx`，例如 `A1` → `%411`、`x.y` → `x%2ey`。这是本地标识编码，不能代替前述详情路径约束。

上游提供的 `route_key`、`routeKey` 或标题不决定本地身份。更改标题不会生成新路由；同名但不同 ID 的记录分别保存。原始 ID 与 Intent Hub 自动分配的本地整数 `id` 是两个不同字段。

## 6. 失败、完整性与本地更新

| 情况 | 当前处理 |
| --- | --- |
| 列表 HTTP/业务失败、缺少 `records` 数组，或列表记录缺少有效 ID | 本轮拉取失败，不进入合并阶段 |
| 单条详情失败、详情 ID 不匹配、必要业务字段缺失 | 记录到 `failed_source_ids`，继续处理其他条目；失败 ID 不按缺失处理 |
| 列表不完整 | 合并可用条目，不据此停用缺失记录 |
| 没有可用条目，包括有效空列表 | 保留本地数据并返回 warning；不会批量停用 |
| 完整且非空的拉取 | 更新本上游记录；在可比较的历史拉取范围内标记缺失并停用，不影响其他上游 |
| URL 或标签筛选范围变更 | 不直接使用旧范围的成员集合判定缺失，避免误停用 |
| 同一 ID 出现在多个标签结果中 | 适配器先去重；重复记录应一致，当前保留后遇到的记录 |
| 合并阶段收到重复原始 ID，或生成标识与其他来源冲突 | 合并事务整批回滚，不接管其他来源数据 |
| 拉取过程中当前上游配置被修改或移除 | 不提交旧配置对应的拉取结果 |

已有人工覆盖继续保留，来源快照会更新；现有本地语料及自动学习记录保持不变。恢复上游字段只支持名称、描述。新增或业务信息变化会产生管理员待处理提醒，人工覆盖不会挡住提醒；无变化拉取不重复提醒。拉取不等于立即完成向量同步。有效内容变更会进入后续索引任务，应分别查看拉取与索引状态。缺失判断的具体范围保护见 [多上游功能说明](../changes/multiple-upstreams/README.md)。

## 7. 与 Intent Hub 管理接口的区别

本文定义的是上游需要实现的 GET API。用户点击“拉取数据”调用的是 Intent Hub 自己的管理接口：

```http
POST /compat/master/routes/upstream-pull
Content-Type: application/json
Authorization: Bearer <管理员登录所得 API Key>

{"upstream_id":"已保存的上游内部ID"}
```

该接口返回 HTTP 202 和任务 ID，后台才开始访问上游。通过 `GET /compat/master/sync-tasks` 查询任务；不传 `upstream_id` 时只拉取默认上游。管理接口要求认证，不意味着上游 GET 接口会收到该凭据。

## 8. 接入验证与依据

接入方应检查：首页不传分页参数时返回第 1 页；多页总数与排序稳定；多标签重复 ID 内容一致；详情 ID 与列表一致；名称和描述字段齐全；空列表和错误响应符合约定。再在 Intent Hub 中保存配置，单独拉取并检查任务结果、本地 `名称.ID` 标识及重复拉取是否无新增。

实现与既有回归入口：

- [上游 HTTP 适配器](../../intent-hub-backend/intent_hub/agent_source.py)：请求、分页、详情；忽略上游语料。
- [身份编码与配置校验](../../intent-hub-backend/intent_hub/upstreams.py)：名称规则、原始 ID 编码。
- [拉取合并](../../intent-hub-backend/intent_hub/services/upstream_agent_service.py)：来源隔离、人工覆盖、缺失保护。
- [适配器与拉取测试](../../intent-hub-backend/tests/test_upstream_agents.py)、[多上游测试](../../intent-hub-backend/tests/test_multiple_upstreams.py)。

本次调整将上游语料改为可选且不导入，保留原始详情响应；未据此声称所有上游都已联调通过。标准格式中比当前兼容行为更严格的约定已在文中明确区分。
