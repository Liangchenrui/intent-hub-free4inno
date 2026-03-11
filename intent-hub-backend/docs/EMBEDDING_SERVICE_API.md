# API 文档 - 文本嵌入服务

本服务提供基于 `Qwen3-Embedding-0.6B` 模型的文本向量化功能。

## 基本信息

- **基础 URL**: `http://localhost:5000` (默认)
- **协议**: HTTP/1.1
- **格式**: JSON

---

## 接口详情

### 1. 获取文本嵌入 (Get Embeddings)

生成输入文本列表的向量表示。

- **端点**: `/get_embeddings`
- **方法**: `POST`
- **Content-Type**: `application/json`

#### 请求参数 (Body)

请求体必须包含嵌套的 `input` 对象，其中包含 `texts` 数组。

| 字段          | 类型          | 必填 | 描述                       |
| :------------ | :------------ | :--- | :------------------------- |
| `input`       | Object        | 是   | 输入数据容器               |
| `input.texts` | Array[String] | 是   | 需要生成嵌入向量的文本列表 |

**请求示例**:

```json
{
  "input": {
    "texts": [
      "你好，世界",
      "人工智能正在改变未来"
    ]
  }
}
```

#### 响应参数

| 字段                             | 类型          | 描述                                 |
| :------------------------------- | :------------ | :----------------------------------- |
| `request_id`                     | String        | 请求的唯一标识符 (UUID)              |
| `usage`                          | Object        | 使用情况统计                         |
| `usage.total_tokens`             | Integer       | 输入文本消耗的总 Token 数            |
| `output`                         | Object        | 输出结果容器                         |
| `output.embeddings`              | Array[Object] | 嵌入向量结果列表                     |
| `output.embeddings[].text_index` | Integer       | 对应输入文本在列表中的索引 (0-based) |
| `output.embeddings[].embedding`  | Array[Float]  | 文本对应的向量数据 (浮点数数组)      |

**成功响应示例 (200 OK)**:

```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "usage": {
    "total_tokens": 15
  },
  "output": {
    "embeddings": [
      {
        "text_index": 0,
        "embedding": [0.123, -0.456, 0.789, ...]
      },
      {
        "text_index": 1,
        "embedding": [-0.987, 0.654, -0.321, ...]
      }
    ]
  }
}
```

#### 错误响应

如果请求格式不正确，将返回 `400 Bad Request`。

**示例 1: 缺少 `input` 字段**

```json
{
  "error": "Missing 'input' field in request body (required format: {\"input\": {\"texts\": [...]}})"
}
```

**示例 2: 缺少 `input.texts` 字段**

```json
{
  "error": "Missing 'input.texts' in request body (required format: {\"input\": {\"texts\": [...]}})"
}
```

**示例 3: 输入文本不是字符串**

```json
{
  "error": "All items in 'input.texts' must be strings"
}
```
