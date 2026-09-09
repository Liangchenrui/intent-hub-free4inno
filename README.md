# Intent Hub

Minimal Agent router. Agents are read from the configured upstream API, synchronized to the existing Qdrant vector format, and queried with a fixed `0.8` threshold.

## Runtime secrets

Copy `.env.example` to an ignored local `.env` and replace its unusable placeholders. The backend reads `AGENT_API_TOKEN`, `QDRANT_API_KEY`, `LLM_API_KEY`, and `AUTH_CODE` exclusively from its environment. Docker Compose maps the shared `INTENT_HUB_AUTH_CODE` value to backend `AUTH_CODE` and to the frontend nginx container.

The settings API and management page expose and persist only non-secret settings. Legacy secret fields in `data/settings.json` are ignored and removed the next time non-secret settings are saved. Secrets must be maintained through the local environment file or 1Panel, never through the management UI.

The browser bundle contains no backend credential. At container startup, the official nginx image renders `nginx.conf.template` and the reverse proxy injects the `Authorization` header for `/api` requests. If the authentication value is absent, the backend rejects every protected request.

## Run

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

For local frontend development, route `/api` through an equivalent trusted reverse proxy; do not place backend credentials in Vite variables or browser code.

See [USER_GUIDE.md](USER_GUIDE.md) and [docs/API.md](docs/API.md).
