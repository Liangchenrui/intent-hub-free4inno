# Intent Hub

Intent Hub 是单工作区意图路由服务，包含 Flask 后端和 Vue 3 管理前端。

## 鉴权

- 管理用户通过 `POST /auth/login` 使用用户名和密码登录，返回的短期 API Key 用于管理接口。
- 外部路由接口 `POST /predict` 使用独立的 `PREDICT_AUTH_KEY`，支持 Bearer、原始 Authorization 或 `X-API-Key`。

## 主要接口

- 路由管理：`/routes`、`/routes/search`、`/routes/{id}`
- 索引：`/reindex`、`/reindex/sync-route`
- 诊断：`/diagnostics/*`
- 设置：`/settings`
- 路由预测：`/predict`

运行数据直接保存在 `intent-hub-backend/data/` 下：`routes.json`、`settings.json` 和 `diagnostics_cache.json`。

```bash
pytest intent-hub-backend/tests -q
cd intent-hub-frontend && npm install && npm run build
```
