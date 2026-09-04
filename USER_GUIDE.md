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

`QDRANT_URL` 与 `EMBEDDING_SERVICE_URL` 必须是完整的 `http://` 或 `https://` URL。默认 Embedding 服务使用 `http://embedding.free4inno.com/embed` 和 `tei` 协议（请求体为 `{"inputs": [...]}`）；自定义 `qwen` 协议地址未包含 `/get_embeddings` 时才会补充该路径。

## 英文诊断

界面切换到 English 后，请求携带 `language=en`，后端会约束诊断建议中的所有自然语言字段使用英文。

## 保存与同步

新增、编辑、删除意图后，本地配置会立即保存，向量索引在后台按意图增量同步。列表中的状态会依次显示“等待同步”“同步中”“已同步”；Qdrant 暂时不可用时，本地修改不会丢失，系统会自动重试并显示失败原因。

手工点击“同步”只会提交后台 hash 检查任务，页面无需等待。任务仅重新生成新增或内容 hash 变化的意图向量，跳过未变化项，并清理已删除项；完成后界面显示新增、更新、删除和跳过数量。模型、向量维度或 Collection 迁移仍应使用显式全量重建能力。

在设置页配置上游 Agent API 后，可以从意图实体页拉取 Agent。拉取操作只更新本地配置，不回写上游，也不立即更新向量。人工修改的上游字段会被标记为覆盖项，后续拉取不会覆盖；点击列表中的差异状态可查看或恢复为最近一次上游快照。

## 数据文件

- `intent-hub-backend/data/routes.json`
- `intent-hub-backend/data/settings.json`
- `intent-hub-backend/data/diagnostics_cache.json`
- `intent-hub-backend/data/sync_tasks.json`
- `intent-hub-backend/data/routes.json.sequence`
