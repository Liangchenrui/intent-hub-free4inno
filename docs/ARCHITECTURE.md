# Architecture

Intent Hub has one Flask service, one Vue administration UI, and one shared runtime workspace.

```text
intent-hub-backend/
├── intent_hub/
│   ├── api/
│   ├── core/
│   └── services/
└── data/
    ├── routes.json
    ├── routes.json.sequence
    ├── settings.json
    ├── diagnostics_cache.json
    └── sync_tasks.json
```

One component manager creates the encoder, Qdrant client, and route manager. Qdrant and embedding endpoints are complete URLs passed without inferred ports. Management login keys and the external `PREDICT_AUTH_KEY` are separate.

Each synced route also has one recovery-only Qdrant point containing the complete `RouteConfig` payload. It is marked with `is_route_metadata=true` and is explicitly excluded from prediction, matching, testing, and diagnostics. Collection recovery reads these records first and only falls back to aggregating legacy utterance payloads when metadata records are absent.

Route configuration is the source of truth and Qdrant is a derived index. Route writes atomically persist `routes.json`, increment a route version, enqueue a durable task in `sync_tasks.json`, and return without waiting for embedding or Qdrant. A single background worker coalesces queued edits, retries transient failures, and marks a route synced only when the indexed version still matches the current local version. Route IDs are stable and monotonically allocated through `routes.json.sequence`.

Manual full reindex remains available for embedding-model or collection migrations. Normal create, update, delete, feedback, import, and repair operations use route-scoped background synchronization. Diagnostics refresh runs as a separate asynchronous phase after indexing, so it does not delay save or index readiness.
