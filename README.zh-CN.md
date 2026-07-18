# Intent Hub

最小 Agent 意图路由服务。Agent 从固定上游 API 只读获取，按原有 Qdrant 向量结构同步，并使用固定 `0.8` 阈值查询。

## 启动

```powershell
cd intent-hub-backend
pip install -e .[dev]
python run.py
```

```powershell
cd intent-hub-frontend
npm install
npm run dev
```

前端仅包含登录、Agent 同步与列表、路由测试和 Qdrant Collection 设置。

接口说明见 [USER_GUIDE.md](USER_GUIDE.md) 与 [docs/API.md](docs/API.md)。

