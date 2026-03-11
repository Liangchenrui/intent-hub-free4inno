# CLAUDE.md

## Build & Run
- Run all (Docker): `docker compose up -d`
- Run all (Docker, China): `docker compose --env-file .env.china up -d --build`
- Backend install: `cd intent-hub-backend && pip install -r requirements.txt`
- Backend run: `cd intent-hub-backend && python run.py`
- Frontend install: `cd intent-hub-frontend && npm install`
- Frontend run: `cd intent-hub-frontend && npm run dev`

## Testing
- Backend tests: `cd intent-hub-backend && pytest`

## Architecture
- Backend: Python 3.9+, Flask, Qdrant
- Frontend: Vue 3, Vite, Element Plus
- Database: Qdrant (Vector DB)
- LLM Integration: LangChain (DeepSeek, OpenAI, Qwen)
