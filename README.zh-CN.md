# Intent Hub 🚀

一个基于向量相似度的静态路由系统，通过语义匹配将用户请求精准分发至对应的 AI Agent。

**[English](README.md)** | **[中文](README.zh-CN.md)**

📹 **视频演示：** [在 YouTube 观看](https://youtu.be/bWHMFci6Pkc?si=z7W_GVkbC3i0_Udp)

---

## 🗺️ 导航与快速开始

### ⚡ 快速一键运行 (推荐)

项目已深度容器化，支持一键部署。

1. **准备环境配置**:
   ```shell
   cp .env.example .env
   ```
   *编辑 `.env` 文件，填写你的 `LLM_API_KEY` (用于自动生成语料) 以及其他配置。*

2. **一键启动**:
   ```shell
   docker compose up -d
   ```
   或使用国内加速镜像配置：
   ```shell
   docker compose --env-file .env.china up -d --build
   ```

启动后：
- **管理后台 (Frontend):** `http://localhost` (默认 80 端口)
- **API 服务 (Backend):** `http://localhost:8000`
- **向量数据库 (Qdrant):** `http://localhost:6333/dashboard`

> **注意**：
> - 首次启动会自动拉取/构建镜像，并下载必要的 Embedding 模型，请确保网络畅通。
> - 系统会自动在根目录创建 `data/` 文件夹，用于持久化存储路由配置和系统设置。

---

## ⚙️ 系统配置

项目支持多种配置方式，优先级为：**环境变量 > 数据库/JSON配置 > 默认值**。

### 环境变量 (.env)
你可以通过根目录的 `.env` 文件快速调整以下核心参数：
- `LLM_API_KEY`: 大模型 API Key（必填，用于语料增强）。
- `LLM_PROVIDER`: 模型供应商 (如 `deepseek`, `qwen`, `openai`)。
- `EMBEDDING_MODEL_NAME`: 使用的向量模型名称。
- `QDRANT_URL`: 向量数据库连接地址。

详见 `.env.example` 文件中的注释说明。

### 数据持久化
所有用户配置和路由数据都存储在 `./data` 目录下：
- `data/routes_config.json`: 存储所有的路由及语料配置。
- `data/settings.json`: 存储系统运行参数。
- `data/env.runtime`: **由系统自动生成**的运行时环境变量文件（当你在浏览器里保存系统配置后会同步更新）。

> 说明：
> - 浏览器里保存系统配置默认写入 `data/settings.json`，并同步生成 `data/env.runtime`（用于容器重启时仍能以环境变量方式加载同一份配置）。
> - 如需关闭该同步：设置环境变量 `INTENT_HUB_ENV_SYNC_ENABLED=false`
> - 如需自定义同步输出路径：设置 `INTENT_HUB_ENV_SYNC_PATH=/app/data/env.runtime`
> - 如需自定义同步字段：设置 `INTENT_HUB_ENV_SYNC_KEYS=QDRANT_URL,LLM_PROVIDER,LLM_API_KEY`

在 Docker 部署模式下，该目录已通过 Volume 挂载，确保数据不随容器销毁而丢失。

---

## 🏗️ 项目架构

本项目采用前后端分离架构，通过向量检索实现毫秒级意图分发。

### 🔹 后端 (Python / Flask)
- **核心框架:** [Python 3.9+](https://www.python.org/) + [Flask](https://flask.palletsprojects.com/)
- **向量检索:** [Qdrant](https://qdrant.tech/) (高性能向量数据库)
- **模型能力:** 
  - Embedding: Qwen-Embedding-0.6B (支持 HuggingFace / 本地加载)
  - LLM: 通过 LangChain 集成 DeepSeek, OpenAI, 通义千问等
- **主要职责:** 意图识别、向量同步、自动语料增强生成、路由管理 API。

### 🔹 前端 (Vue / Vite)
- **核心框架:** [Vue 3](https://vuejs.org/) + [Vite](https://vitejs.dev/)
- **UI 组件库:** [Element Plus](https://element-plus.org/)
- **主要职责:** 路由 CRUD 可视化、语料生成交互、系统配置、向量匹配效果测试。

---

## 📂 目录结构

```text
intenthub/
├── data/                  # 持久化数据 (路由配置、系统设置)
├── intent-hub-backend/    # 后端源代码 (Python/Flask)
│   ├── intent_hub/        # 核心逻辑 (编码、检索、服务层)
│   ├── tests/             # 单元测试
│   └── run.py             # 服务启动入口
├── intent-hub-frontend/   # 前端源代码 (Vue/Vite)
│   ├── src/               # 页面、组件、状态管理
│   └── vite.config.ts     # 构建配置
├── docker-compose.yml     # 全栈容器化编排
├── .env.example           # 环境变量配置模板
└── README.md              # 本说明文件 (项目导航)
```

---

## 📄 License
Distributed under the MIT License. See `LICENSE` for more information.
