# Intent Hub 🚀

Intent Hub is a static routing system based on vector similarity. It matches user input semantically and dispatches the request to the right downstream AI Agent.

**[English](README.md)** | **[中文](README.zh-CN.md)**

📹 **Video Demo:** [Watch on YouTube](https://youtu.be/bWHMFci6Pkc?si=z7W_GVkbC3i0_Udp)

---

## Overview

- This repository contains the admin frontend and the Flask backend.
- Intent routing depends on an external embedding service and a reachable Qdrant instance.
- Route data and system settings are persisted under `intent-hub-backend/data/`.

---

## Quick Start

### Prerequisites

- Docker and Docker Compose
- A reachable Qdrant service
- A reachable embedding service
- An LLM API key if you want utterance generation or diagnostics repair

### Start with Docker Compose

1. Optional: copy the template if you need custom build mirrors or image prefixes.
   ```shell
   cp .env.example .env
   ```
2. Start the frontend and backend containers.
   ```shell
   docker compose up -d --build
   ```
   For China mirror settings:
   ```shell
   docker compose --env-file .env.china up -d --build
   ```
3. Open the admin UI and complete runtime settings, or write them directly into `intent-hub-backend/data/settings.json`.

After startup:

- Frontend: `http://localhost`
- Backend API: `http://localhost:8000`

Notes:

- `docker-compose.yml` in this repository starts `intent-hub-frontend` and `intent-hub-backend`.
- Qdrant and the embedding service are external dependencies for this repo and must already be reachable from the backend.
- Runtime files are stored in `intent-hub-backend/data/`.

---

## Route Contract

Each intent entity now includes a required `route_key`. This is the stable identifier that downstream systems should use for request routing.

Rules and behavior:

- `route_key` is required on create, update, import, and utterance generation requests.
- `route_key` must be unique across routes.
- Normalization is intentionally loose: trim, lowercase, replace whitespace with `.`, collapse repeated dots, trim leading and trailing dots.
- Changing `route_key` is allowed, but it should be treated as a routing contract change for downstream callers.
- Legacy `routes.json` entries without `route_key` are migrated automatically on load and written back to disk.

Example route config:

```json
{
  "id": 1,
  "name": "Weather Service",
  "route_key": "weather.query",
  "description": "Return weather information for a city",
  "utterances": ["what is the weather in Beijing"],
  "negative_samples": [],
  "score_threshold": 0.85,
  "negative_threshold": 0.95
}
```

Example `/predict` response:

```json
[
  {
    "id": 1,
    "name": "Weather Service",
    "route_key": "weather.query",
    "score": 0.93
  }
]
```

If no route matches the threshold, the backend returns the fallback route with `route_key: "fallback.default"`.

---

## Configuration and Data

Runtime state is stored in `intent-hub-backend/data/`:

- `intent-hub-backend/data/routes.json`: route definitions
- `intent-hub-backend/data/settings.json`: runtime system settings
- `intent-hub-backend/data/diagnostics_cache.json`: cached diagnostics results

Typical settings managed by the backend:

- `QDRANT_URL`
- `QDRANT_COLLECTION`
- `EMBEDDING_SERVICE_URL`
- `LLM_PROVIDER`
- `LLM_API_KEY`
- `PREDICT_AUTH_KEY`
- `DEFAULT_USERNAME`
- `DEFAULT_PASSWORD`

`README` and the API docs assume the persisted settings file is the runtime source of truth.

---

## Production Deployment

The production deployment described in `Intent Hub 部署文档.docx` uses these services on Hufu:

- `intent-hub-frontend`
- `intent-hub-backend`
- `intent-hub-embedding`
- `qdrant`

### Upgrade Flow

1. Before upgrading, enter the old Intent Hub instance and save or export the current route configuration.
2. Build the frontend artifact:
   ```shell
   cd intent-hub-frontend
   npm install
   npm run build:prod
   ```
   This generates `dist.tar.gz`. Upload the updated mounted files for the Hufu frontend service:
   `https://hf.free4inno.com/#/project/container/detail/732`
3. Build and publish the backend image:
   ```shell
   cd intent-hub-backend
   docker build -f Dockerfile .
   docker tag intent-hub-backend:latest crpi-v8ss93lfn0gwwreg.cn-hangzhou.personal.cr.aliyuncs.com/free4inno-lcr/intent-hub:2.0.0
   docker push crpi-v8ss93lfn0gwwreg.cn-hangzhou.personal.cr.aliyuncs.com/free4inno-lcr/intent-hub:2.0.0
   ```
   Then update the backend service image in Hufu:
   `https://hf.free4inno.com/#/project/container/detail/720`
4. If the embedding model or embedding logic changes, update the embedding project and then refresh the embedding service image:
   - Repo: `https://gitee.com/free4inno-bupt/embedding-zpoint`
   - Service: `https://hf.free4inno.com/#/project/container/detail/733`
5. After rollout, verify frontend access, backend health, route import, and `/predict` responses including `route_key`.

---

## Project Layout

```text
intent-hub/
├── intent-hub-backend/       # Flask backend
│   ├── intent_hub/           # Core application code
│   ├── data/                 # Runtime data
│   ├── docs/                 # Backend docs
│   └── tests/                # Backend tests
├── intent-hub-frontend/      # Vue 3 + Vite admin UI
│   ├── src/                  # Frontend source
│   └── dist/                 # Frontend build output
├── docker-compose.yml        # Local frontend/backend compose
├── .env.example              # Optional compose/build template
├── README.md
└── README.zh-CN.md
```

---

## Runtime Notes

1. `POST /v1/route` returns only route matching results.
2. `POST /v1/dispatch` returns route matching + dispatch suggestion payload.
3. Current `dispatch` is suggestion-only (`status: not_executed`), no real tool execution yet.

## Backend CLI Install

```bash
cd intent-hub-backend
pip install -e .
```

After install, both commands are available:

```bash
intent-hub --help
intenthub --help
```

---

## License

Distributed under the MIT License. See `LICENSE` for details.
