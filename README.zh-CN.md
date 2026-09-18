# Intent Hub

Intent Hub 是单工作区意图路由服务，包含 Flask 后端和 Vue 3 管理前端。

## 鉴权

- 管理用户通过 `POST /auth/login` 使用用户名和密码登录，返回的短期 API Key 用于管理接口。
- 外部路由接口 `POST /predict` 使用独立的 `PREDICT_AUTH_KEY`，支持 Bearer、原始 Authorization 或 `X-API-Key`。

## 主要接口

- 路由管理：`/routes`、`/routes/search`、`/routes/{id}`
- 索引：自动路由级同步、`/reindex`、`/reindex/sync-route`、`/sync-tasks`
- 诊断：`/diagnostics/*`
- 设置：`/settings`
- 路由预测：`/predict`

运行数据直接保存在 `intent-hub-backend/data/` 下：`routes.sqlite3`、`settings.json` 和 `diagnostics_cache.json`。

```bash
pytest intent-hub-backend/tests -q
cd intent-hub-frontend && npm install && npm run build
```


## master / BUPT 统一版本

两套 API 共用 SQLite 仓库、路由核心和同步队列。`API_COMPAT_PROFILE=master`（默认）或 `bupt` 决定根路径兼容接口；`/compat/master/*` 和 `/compat/bupt/*` 始终可显式访问。管理台统一使用 master 命名空间，固定登录凭据为 `admin / telestar`，不需要 `DEFAULT_PASSWORD` 环境变量。LLM API Key 在设置页配置并保存到本地；BUPT 访问码 `AUTH_CODE` 及其他服务密钥仍通过进程环境设置。

已有数据的实例请遵循[迁移与兼容说明](docs/changes/branch-unification/README.md)。迁移后内部 ID 可能变化，BUPT 旧索引须重新构建。Docker Compose 将认证及服务密钥从环境传入容器；本次暂不部署。
