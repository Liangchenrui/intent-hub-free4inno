# Repository instructions

- Backend: `intent-hub-backend/`; frontend: `intent-hub-frontend/`.
- Agents are read only from the upstream API. Do not add local Agent write paths.
- Keep the existing Qdrant positive and negative payload fields unchanged.
- Qdrant URL, API key, embedding service, upstream URL, token, and `0.8` threshold are fixed. Only the collection is writable.
- Backend verification: `pytest intent-hub-backend/tests -q`.
- Frontend verification: run `npm run build` in `intent-hub-frontend/`.

