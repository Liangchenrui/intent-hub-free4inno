# Intent Hub 使用指南

## 登录管理台

访问 `/login`，使用基础用户名和密码登录。浏览器随后使用短期 `api_key` 访问路由、诊断和设置接口。

## 调用路由接口

在设置页配置 `PREDICT_AUTH_KEY`，然后调用：

```bash
curl -X POST http://localhost:5000/predict \
  -H "Authorization: Bearer <PREDICT_AUTH_KEY>" \
  -H "Content-Type: application/json" \
  -d '{"text":"帮我整理知识库"}'
```

## 服务地址

`QDRANT_URL` 与 `EMBEDDING_SERVICE_URL` 必须是完整的 `http://` 或 `https://` URL。系统不会追加默认端口；Embedding URL 未包含 `/get_embeddings` 时只补充该路径。

## 英文诊断

界面切换到 English 后，请求携带 `language=en`，后端会约束诊断建议中的所有自然语言字段使用英文。

## 数据文件

- `intent-hub-backend/data/routes.json`
- `intent-hub-backend/data/settings.json`
- `intent-hub-backend/data/diagnostics_cache.json`
