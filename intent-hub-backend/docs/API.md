# Intent Hub API 接口文档

## 基础信息

- **Base URL**: `http://localhost:8000`（Docker Compose 对外端口，服务容器内监听 `5000`）
- **认证方式**:
  1. **管理接口认证**
     - 请求头：`Authorization: Bearer <api_key>` 或 `X-API-Key: <api_key>`
     - 通过 `/auth/login` 获取短期有效的 API Key
  2. **预测接口认证**
     - 优先使用 `PREDICT_AUTH_KEY`
     - 支持 `Authorization: Bearer <predict_key>`、`X-API-Key: <predict_key>`，也兼容直接把原始 key 放在 `Authorization` 头里
     - 当 `PREDICT_AUTH_KEY` 为空且 `AUTH_ENABLED=false` 时，预测接口可匿名访问
     - 当 `AUTH_ENABLED=true` 时，预测接口也接受有效的管理 API Key，方便后台联调

## 接口列表

### 1. 健康检查

**接口**: `GET /health`

**鉴权**: 否

**响应**:

```json
{
  "status": "ok",
  "qdrant_ready": true,
  "encoder_ready": true,
  "route_manager_ready": true,
  "auth_enabled": true
}
```

---

### 2. 登录

**接口**: `POST /auth/login`

**鉴权**: 否

**请求体**:

```json
{
  "username": "admin",
  "password": "your_password"
}
```

**说明**:

- 默认用户名：`admin`
- 默认密码：`123456`
- 用户名和密码保存在 `settings.json` 的 `DEFAULT_USERNAME`、`DEFAULT_PASSWORD` 中

**响应** (200):

```json
{
  "api_key": "your-api-key-here",
  "message": "请妥善保管此API key，后续请求需要在请求头中提供 Authorization: Bearer <key> 或 X-API-Key: <key>"
}
```

**错误响应** (401):

```json
{
  "error": "认证失败",
  "detail": "用户名或密码错误"
}
```

---

### 3. 路由预测

**接口**: `POST /predict`

**鉴权**: 是（`PREDICT_AUTH_KEY` 或有效 API Key）

**请求头**:

```text
Authorization: Bearer <predict_key>
```

**请求体**:

```json
{
  "text": "北京今天天气如何？"
}
```

**响应** (200):

返回所有相似度达到各自阈值的路由，按分数降序排列。每个命中路由都会带上稳定的 `route_key`。

```json
[
  {
    "id": 1,
    "name": "天气服务",
    "route_key": "weather.query",
    "score": 0.93
  }
]
```

**说明**:

- 系统先检索 Top-K 候选，再按路由 ID 聚合，取每个路由的最高分
- 查询如果命中过高相似度的负例样本，会先排除对应路由
- 只有分数大于等于该路由 `score_threshold` 的结果才会返回
- 如果没有路由满足阈值，则返回默认回退路由：

```json
[
  {
    "id": 0,
    "name": "none",
    "route_key": "fallback.default",
    "score": null
  }
]
```

---

### 4. 获取所有路由

**接口**: `GET /routes`

**鉴权**: 是

**响应** (200):

```json
[
  {
    "id": 1,
    "name": "天气服务",
    "route_key": "weather.query",
    "description": "返回城市的天气信息",
    "utterances": [
      "北京现在天气如何",
      "上海明天下雨吗"
    ],
    "negative_samples": [],
    "score_threshold": 0.85,
    "negative_threshold": 0.95
  }
]
```

---

### 5. 搜索路由

**接口**: `GET /routes/search`

**鉴权**: 是

**查询参数**:

- `q`（string，可选）：在路由名称、描述和例句中搜索；为空时返回全部路由

**响应** (200):

返回结构与 `GET /routes` 一致。

---

### 6. 创建路由

**接口**: `POST /routes`

**鉴权**: 是

**请求体**:

```json
{
  "id": 0,
  "name": "订单查询",
  "route_key": "order.query",
  "description": "提供订单查询服务",
  "utterances": [
    "查询订单",
    "我的订单在哪里"
  ],
  "negative_samples": [],
  "score_threshold": 0.75,
  "negative_threshold": 0.95
}
```

**参数说明**:

- `id`（int）：传 `0` 时自动分配新 ID；传非 `0` 时要求该路由已存在，否则报错
- `name`（string，必填）：路由名称
- `route_key`（string，必填）：稳定业务路由标识，必须唯一
- `description`（string，可选）：路由描述
- `utterances`（string[]，必填）：示例语句列表
- `negative_samples`（string[]，可选）：负例语句列表
- `score_threshold`（float，可选）：命中阈值，范围 `0.0-1.0`
- `negative_threshold`（float，可选）：负例排除阈值，范围 `0.0-1.0`

**route_key 处理规则**:

- 标准化规则较宽松：去首尾空格、转小写、空白转 `.`、连续 `.` 折叠、首尾 `.` 去除
- 不做严格格式限制，但必须非空且唯一

**响应** (201):

返回保存后的完整路由对象。

**错误响应** (400):

```json
{
  "error": "请求参数错误",
  "detail": "route_key 'order.query' already exists"
}
```

---

### 7. 更新路由

**接口**: `PUT /routes/<route_id>`

**鉴权**: 是

**路径参数**:

- `route_id`（int）：路由 ID

**请求体**:

```json
{
  "id": 1,
  "name": "天气服务",
  "route_key": "weather.query",
  "description": "返回城市的天气信息",
  "utterances": [
    "北京现在天气如何",
    "新增的示例语句"
  ],
  "negative_samples": [],
  "score_threshold": 0.85,
  "negative_threshold": 0.95
}
```

**说明**:

- 请求体需要提供完整的 `RouteConfig`
- 允许修改 `route_key`，但这会改变下游路由契约，前端应给予告警提示

**响应** (200):

返回更新后的完整路由对象。

**错误响应** (404):

```json
{
  "error": "路由不存在",
  "detail": "Route ID 1 does not exist"
}
```

---

### 8. 删除路由

**接口**: `DELETE /routes/<route_id>`

**鉴权**: 是

**响应** (200):

```json
{
  "message": "路由 1 已删除"
}
```

---

### 9. 重新索引

**接口**: `POST /reindex`

**鉴权**: 是

**请求体**（可选）:

```json
{
  "force_full": false
}
```

**响应** (200):

```json
{
  "message": "重新索引完成",
  "updated_count": 2,
  "total_count": 3
}
```

---

### 10. 生成例句（LLM）

**接口**: `POST /routes/generate-utterances`

**鉴权**: 是

**请求体**:

```json
{
  "id": 1,
  "name": "天气服务",
  "route_key": "weather.query",
  "description": "返回城市的天气信息",
  "count": 5,
  "utterances": [
    "北京现在天气如何",
    "上海明天下雨吗"
  ]
}
```

**参数说明**:

- `id`（int，必填）：路由 ID
- `name`（string，必填）：路由名称
- `route_key`（string，必填）：业务路由标识
- `description`（string，可选）：路由描述
- `count`（int，可选）：生成数量，范围 `1-50`
- `utterances`（string[]，可选）：参考例句，仅在该路由不存在时使用

**响应** (200):

返回一个 `RouteConfig` 对象，其中包含原示例和新生成的例句，并保留 `route_key`。

```json
{
  "id": 1,
  "name": "天气服务",
  "route_key": "weather.query",
  "description": "返回城市的天气信息",
  "utterances": [
    "北京现在天气如何",
    "上海明天下雨吗",
    "广州今天会下雨吗",
    "查询深圳天气"
  ],
  "negative_samples": [],
  "score_threshold": 0.85,
  "negative_threshold": 0.95
}
```

---

### 11. 获取系统设置

**接口**: `GET /settings`

**鉴权**: 是

**响应** (200):

```json
{
  "QDRANT_URL": "http://localhost:6333",
  "QDRANT_COLLECTION": "intent_hub_routes",
  "QDRANT_API_KEY": null,
  "EMBEDDING_SERVICE_URL": "http://192.168.33.1:30122",
  "EMBEDDING_MODEL_NAME": "Qwen/Qwen3-Embedding-0.6B",
  "EMBEDDING_DEVICE": "cpu",
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": null,
  "LLM_BASE_URL": "https://api.deepseek.com",
  "LLM_MODEL": "deepseek-chat",
  "LLM_TEMPERATURE": 0.7,
  "DEEPSEEK_API_KEY": null,
  "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
  "DEEPSEEK_MODEL": "deepseek-chat",
  "UTTERANCE_GENERATION_PROMPT": "...",
  "AGENT_REPAIR_PROMPT": "...",
  "AUTH_ENABLED": true,
  "PREDICT_AUTH_KEY": null,
  "DEFAULT_USERNAME": "admin",
  "DEFAULT_PASSWORD": "123456",
  "BATCH_SIZE": 32,
  "DEFAULT_ROUTE_ID": 0,
  "DEFAULT_ROUTE_NAME": "none",
  "DEFAULT_ROUTE_KEY": "fallback.default",
  "REGION_THRESHOLD_SIGNIFICANT": 0.0,
  "INSTANCE_THRESHOLD_AMBIGUOUS": 0.0
}
```

---

### 12. 更新系统设置

**接口**: `POST /settings`

**鉴权**: 是

**说明**:

- 只需要提交要更新的字段
- 所有配置会持久化到 `data/settings.json`
- 更新后系统会重新初始化核心组件

**请求体**:

```json
{
  "QDRANT_URL": "http://qdrant:6333",
  "EMBEDDING_SERVICE_URL": "http://embedding-service:30122",
  "LLM_PROVIDER": "deepseek",
  "LLM_API_KEY": "your-api-key",
  "PREDICT_AUTH_KEY": "predict-secret"
}
```

**响应** (200):

```json
{
  "message": "配置更新成功，组件已重新加载",
  "settings": {
    "QDRANT_URL": "http://qdrant:6333",
    "EMBEDDING_SERVICE_URL": "http://embedding-service:30122",
    "LLM_PROVIDER": "deepseek",
    "PREDICT_AUTH_KEY": "predict-secret"
  }
}
```

---

## 错误响应格式

```json
{
  "error": "错误类型",
  "detail": "详细错误信息"
}
```

常见状态码：

- `200`: 成功
- `201`: 创建成功
- `400`: 请求参数错误
- `401`: 认证失败
- `404`: 资源不存在
- `500`: 服务器内部错误

---

## 数据模型

### RouteConfig

```typescript
{
  id: number;
  name: string;
  route_key: string;
  description: string;
  utterances: string[];
  negative_samples: string[];
  score_threshold: number;
  negative_threshold: number;
}
```

### PredictRequest

```typescript
{
  text: string;
}
```

### PredictResponse

```typescript
{
  id: number;
  name: string;
  route_key: string;
  score?: number;
}
```

### GenerateUtterancesRequest

```typescript
{
  id: number;
  name: string;
  route_key: string;
  description?: string;
  count?: number;
  utterances?: string[];
}
```

### Settings

```typescript
{
  QDRANT_URL: string;
  QDRANT_COLLECTION: string;
  QDRANT_API_KEY?: string | null;
  EMBEDDING_SERVICE_URL: string;
  EMBEDDING_MODEL_NAME: string;
  EMBEDDING_DEVICE: string;
  LLM_PROVIDER: string;
  LLM_API_KEY?: string | null;
  LLM_BASE_URL?: string | null;
  LLM_MODEL?: string | null;
  LLM_TEMPERATURE: number;
  DEEPSEEK_API_KEY?: string | null;
  DEEPSEEK_BASE_URL?: string | null;
  DEEPSEEK_MODEL?: string | null;
  UTTERANCE_GENERATION_PROMPT: string;
  AGENT_REPAIR_PROMPT: string;
  AUTH_ENABLED: boolean;
  PREDICT_AUTH_KEY?: string | null;
  DEFAULT_USERNAME: string;
  DEFAULT_PASSWORD: string;
  BATCH_SIZE: number;
  DEFAULT_ROUTE_ID: number;
  DEFAULT_ROUTE_NAME: string;
  DEFAULT_ROUTE_KEY: string;
  REGION_THRESHOLD_SIGNIFICANT: number;
  INSTANCE_THRESHOLD_AMBIGUOUS: number;
}
```
