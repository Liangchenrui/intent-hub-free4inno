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
    ├── settings.json
    └── diagnostics_cache.json
```

One component manager creates the encoder, Qdrant client, and route manager. Qdrant and embedding endpoints are complete URLs passed without inferred ports. Management login keys and the external `PREDICT_AUTH_KEY` are separate.

Each synced route also has one recovery-only Qdrant point containing the complete `RouteConfig` payload. It is marked with `is_route_metadata=true` and is explicitly excluded from prediction, matching, testing, and diagnostics. Collection recovery reads these records first and only falls back to aggregating legacy utterance payloads when metadata records are absent.
