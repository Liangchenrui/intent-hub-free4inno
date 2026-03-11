# Intent Hub 🚀

A static routing system based on vector similarity that dispatches user requests to the right AI Agent via semantic matching.

**[English](README.md)** | **[中文](README.zh-CN.md)**

📹 **Video Demo:** [Watch on YouTube](https://youtu.be/bWHMFci6Pkc?si=z7W_GVkbC3i0_Udp)

---

## 🗺️ Navigation & Quick Start

### ⚡ One-Click Run (Recommended)

The project is fully containerized and supports one-command deployment.

1. **Prepare environment**:
   ```shell
   cp .env.example .env
   ```
   *Edit `.env` and set your `LLM_API_KEY` (for auto corpus generation) and other options.*

2. **Start everything**:
   ```shell
   docker compose up -d
   ```
   Or with China mirror config:
   ```shell
   docker compose --env-file .env.china up -d --build
   ```

After startup:
- **Admin UI (Frontend):** `http://localhost` (port 80 by default)
- **API (Backend):** `http://localhost:8000`
- **Vector DB (Qdrant):** `http://localhost:6333/dashboard`

> **Note:**
> - First run will pull/build images and download the Embedding model; ensure network access.
> - A `data/` directory is created at the project root for persisting routes and settings.

---

## ⚙️ Configuration

Configuration priority: **Environment variables > DB/JSON config > Defaults.**

### Environment variables (.env)

Key options in the root `.env` file:
- `LLM_API_KEY`: LLM API key (required for corpus enhancement).
- `LLM_PROVIDER`: Provider (e.g. `deepseek`, `qwen`, `openai`).
- `EMBEDDING_MODEL_NAME`: Embedding model name.
- `QDRANT_URL`: Qdrant connection URL.

See comments in `.env.example` for details.

### Data persistence

User config and route data live under `./data`:
- `data/routes_config.json`: Routes and corpus config.
- `data/settings.json`: System settings.
- `data/env.runtime`: **Auto-generated** runtime env file (updated when you save settings in the UI).

> - Saving settings in the UI writes to `data/settings.json` and updates `data/env.runtime` so containers keep the same config after restart.
> - Disable sync: set `INTENT_HUB_ENV_SYNC_ENABLED=false`.
> - Custom sync path: `INTENT_HUB_ENV_SYNC_PATH=/app/data/env.runtime`.
> - Custom sync keys: `INTENT_HUB_ENV_SYNC_KEYS=QDRANT_URL,LLM_PROVIDER,LLM_API_KEY`.

In Docker, this directory is mounted as a volume so data survives container removal.

---

## 🏗️ Architecture

Frontend/backend split with vector search for fast intent routing.

### 🔹 Backend (Python / Flask)
- **Stack:** [Python 3.9+](https://www.python.org/) + [Flask](https://flask.palletsprojects.com/)
- **Vector store:** [Qdrant](https://qdrant.tech/)
- **Models:**
  - Embedding: Qwen-Embedding-0.6B (HuggingFace / local)
  - LLM: LangChain integration for DeepSeek, OpenAI, Qwen, etc.
- **Responsibilities:** Intent recognition, vector sync, auto corpus generation, route management API.

### 🔹 Frontend (Vue / Vite)
- **Stack:** [Vue 3](https://vuejs.org/) + [Vite](https://vitejs.dev/)
- **UI:** [Element Plus](https://element-plus.org/)
- **Responsibilities:** Route CRUD UI, corpus generation, system config, vector match testing.

---

## 📂 Project layout

```text
intenthub/
├── data/                  # Persisted data (routes, settings)
├── intent-hub-backend/    # Backend (Python/Flask)
│   ├── intent_hub/        # Core (encoding, search, services)
│   ├── tests/             # Unit tests
│   └── run.py             # Entry point
├── intent-hub-frontend/   # Frontend (Vue/Vite)
│   ├── src/               # Pages, components, state
│   └── vite.config.ts    # Build config
├── docker-compose.yml     # Full-stack compose
├── .env.example           # Env template
└── README.md              # This file
```

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for details.
