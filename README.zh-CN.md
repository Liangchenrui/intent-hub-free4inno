# Intent Hub 🚀

Intent Hub 是一个基于向量相似度的静态路由系统，通过语义匹配将用户请求分发到正确的下游 AI Agent。

**[English](README.md)** | **[中文](README.zh-CN.md)**

📹 **视频演示：** [在 YouTube 观看](https://youtu.be/bWHMFci6Pkc?si=z7W_GVkbC3i0_Udp)

---

## 项目概览

- 本仓库包含管理后台前端和 Flask 后端。
- 意图路由依赖外部 Embedding 服务和可访问的 Qdrant。
- 路由数据与系统设置持久化在 `intent-hub-backend/data/`。

---

## 快速开始

### 前置条件

- 已安装 Docker 与 Docker Compose
- 可访问的 Qdrant 服务
- 可访问的 Embedding 服务
- 如果需要例句生成或诊断修复，还需要可用的 LLM API Key

### 使用 Docker Compose 启动

1. 如需自定义构建镜像源或镜像前缀，可先复制模板：
   ```shell
   cp .env.example .env
   ```
2. 启动前后端容器：
   ```shell
   docker compose up -d --build
   ```
   国内镜像配置可使用：
   ```shell
   docker compose --env-file .env.china up -d --build
   ```
3. 启动后，在管理后台中补充运行时配置，或者直接编辑 `intent-hub-backend/data/settings.json`。

启动后访问：

- 前端管理后台：`http://localhost`
- 后端 API：`http://localhost:8000`

说明：

- 当前仓库中的 `docker-compose.yml` 只启动 `intent-hub-frontend` 和 `intent-hub-backend`。
- Qdrant 与 Embedding 服务是外部依赖，需要由后端能够访问。
- 运行时文件保存在 `intent-hub-backend/data/`。

---

## 路由契约

现在每个意图实体都包含必填的 `route_key`，它是提供给下游系统使用的稳定路由标识。

当前规则与行为：

- 创建、更新、导入、生成例句时都必须提供 `route_key`。
- `route_key` 在全局范围内必须唯一。
- 标准化规则保持宽松：去首尾空格、转小写、空白替换为 `.`、连续 `.` 折叠、移除首尾 `.`。
- 允许修改 `route_key`，但应视为下游路由契约变更。
- 旧版 `routes.json` 中缺失 `route_key` 的路由会在加载时自动补齐并回写。

路由配置示例：

```json
{
  "id": 1,
  "name": "天气服务",
  "route_key": "weather.query",
  "description": "返回城市的天气信息",
  "utterances": ["北京现在天气如何"],
  "negative_samples": [],
  "score_threshold": 0.85,
  "negative_threshold": 0.95
}
```

`/predict` 返回示例：

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

如果没有命中任何路由，后端会返回默认回退路由，`route_key` 为 `fallback.default`。

---

## 配置与数据

运行时状态保存在 `intent-hub-backend/data/`：

- `intent-hub-backend/data/routes.json`：路由定义
- `intent-hub-backend/data/settings.json`：运行时系统配置
- `intent-hub-backend/data/diagnostics_cache.json`：诊断缓存结果

后端重点配置项包括：

- `QDRANT_URL`
- `QDRANT_COLLECTION`
- `EMBEDDING_SERVICE_URL`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `PREDICT_AUTH_KEY`
- `DEFAULT_USERNAME`
- `DEFAULT_PASSWORD`

当前 README 与接口文档都以持久化的 `settings.json` 作为运行时配置真相源。

---

## 生产部署

`Intent Hub 部署文档.docx` 中描述的 Hufu 生产部署包含以下服务：

- `intent-hub-frontend`
- `intent-hub-backend`
- `intent-hub-embedding`
- `qdrant`

### 升级流程

1. 升级前先进入旧版 Intent Hub，保存或导出当前路由配置。
2. 构建前端发布产物：
   ```shell
   cd intent-hub-frontend
   npm install
   npm run build:prod
   ```
   该命令会生成 `dist.tar.gz`，然后将新的挂载文件更新到 Hufu 前端服务：
   `https://hf.free4inno.com/#/project/container/detail/732`
3. 构建并推送后端镜像：
   ```shell
   cd intent-hub-backend
   docker build -f Dockerfile .
   docker tag intent-hub-backend:latest crpi-v8ss93lfn0gwwreg.cn-hangzhou.personal.cr.aliyuncs.com/free4inno-lcr/intent-hub:2.0.0
   docker push crpi-v8ss93lfn0gwwreg.cn-hangzhou.personal.cr.aliyuncs.com/free4inno-lcr/intent-hub:2.0.0
   ```
   随后在 Hufu 中更新后端服务镜像地址：
   `https://hf.free4inno.com/#/project/container/detail/720`
4. 如果 Embedding 模型或 Embedding 逻辑发生变化，需要同步更新 Embedding 项目并刷新服务镜像：
   - 仓库：`https://gitee.com/free4inno-bupt/embedding-zpoint`
   - 服务：`https://hf.free4inno.com/#/project/container/detail/733`
5. 发布完成后，检查前端访问、后端健康状态、路由导入，以及 `/predict` 返回中的 `route_key` 是否正确。

---

## 目录结构

```text
intent-hub/
├── intent-hub-backend/       # Flask 后端
│   ├── intent_hub/           # 核心应用代码
│   ├── data/                 # 运行时数据
│   ├── docs/                 # 后端文档
│   └── tests/                # 后端测试
├── intent-hub-frontend/      # Vue 3 + Vite 管理后台
│   ├── src/                  # 前端源码
│   └── dist/                 # 前端构建产物
├── docker-compose.yml        # 本地前后端编排
├── .env.example              # 可选的 compose/build 模板
├── README.md
└── README.zh-CN.md
```

---

## 多租户运行时说明（更新）

1. `POST /v1/route`：只返回路由匹配结果。  
2. `POST /v1/dispatch`：返回路由匹配 + 分发建议（当前不执行真实工具）。  
3. Skill 扫描支持 `scan/apply`，`apply` 模式下同 `route_key` 会跳过，不会覆盖。  

## 后端包安装与命令

在 `intent-hub-backend` 目录执行：

```bash
pip install -e .
```

安装后可用命令：

```bash
intent-hub --help
intenthub --help
```

---

## 独立 CLI 包

如果用户只需要连接远程部署的 Intent Hub 服务，应安装独立的 intent-hub-cli 包，而不是后端服务包。

当前可直接本地按 pip 包方式安装：

```bash
pip install ./intent-hub-cli
```

如果希望先打包再安装：

```bash
cd intent-hub-cli
python -m pip install -U build
python -m build
pip install dist/intent_hub_cli-0.1.0-py3-none-any.whl
```

后续发布到 PyPI 后，目标安装方式为：

```bash
pip install intent-hub-cli
```

## License

Distributed under the MIT License. See `LICENSE` for more information.
