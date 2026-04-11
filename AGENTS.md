# Repository Guidelines

## Project Structure & Module Organization
This repository is split into two apps plus root-level deployment files. `intent-hub-backend/` contains the Flask service, with core code in `intent_hub/`, tests in `tests/`, docs in `docs/`, and runtime data in `data/`. `intent-hub-frontend/` contains the Vue 3 + Vite admin UI, with application code in `src/`, static files in `public/`, and build output in `dist/`. Root files such as `docker-compose.yml`, `.env.example`, and `README.md` define the full-stack workflow.

## Build, Test, and Development Commands
Use Docker for the full stack:
`cp .env.example .env` then `docker compose up -d`

Backend local setup:
`cd intent-hub-backend`
`pip install -e ".[dev]"`
`python run.py`

Backend quality checks:
`pytest`
`pytest --cov=intent_hub`
`black .`
`flake8`
`mypy intent_hub`

Frontend local setup:
`cd intent-hub-frontend`
`npm install`
`npm run dev`
`npm run build`

`npm run build` is also the main frontend verification step because no separate frontend test runner is configured here.

## Coding Style & Naming Conventions
Python uses 4-space indentation, `snake_case` for modules/functions, and Black with a 100-character line length. Keep backend packages under `intent_hub/` and name tests `test_*.py`. Vue and TypeScript files use 2-space indentation in practice, `PascalCase` for view/component files such as `Settings.vue`, and `camelCase` for variables and helpers. Follow the existing style in the file you touch instead of reformatting unrelated code.

## Testing Guidelines
Backend tests use `pytest`; place new coverage in `intent-hub-backend/tests/` and prefer focused unit tests near config, API, and routing behavior. Name tests like `test_config_defaults`. For frontend changes, run `npm run build` and manually smoke-test login, agent list, diagnostics, and settings flows.

## Commit & Pull Request Guidelines
Recent history follows concise conventional prefixes such as `feat:`, `fix:`, `refactor:`, and `chore:`. Keep commit subjects short, imperative, and scoped to one change. PRs should explain behavior changes, note any config or data migration impact, link related issues, and include screenshots for UI changes. List the commands you ran to validate the change.

## Security & Configuration Tips
Start from `.env.example` or `.env.china`; never commit real secrets. Treat `intent-hub-backend/data/` and generated runtime files as environment-specific state, not source of truth.
