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

The embedding client supports two explicit wire formats: `qwen` keeps the existing `/get_embeddings` request/response contract, while `tei` sends `{"inputs": [...]}` to the exact configured endpoint and accepts a plain embedding array. The default Free4inno service uses the TEI-compatible `http://embedding.free4inno.com/embed` endpoint. The protocol is never guessed at runtime.

Each synced route also has one recovery-only Qdrant point containing the complete `RouteConfig` payload. It is marked with `is_route_metadata=true` and is explicitly excluded from prediction, matching, testing, and diagnostics. Collection recovery reads these records first and only falls back to aggregating legacy utterance payloads when metadata records are absent.

Route configuration is the source of truth and Qdrant is a derived index. Route writes atomically persist `routes.json`, increment a route version, enqueue a durable task in `sync_tasks.json`, and return without waiting for embedding or Qdrant. A single background worker coalesces queued edits, retries transient failures, and marks a route synced only when the indexed version still matches the current local version. Route IDs are stable and monotonically allocated through `routes.json.sequence`.

The normal manual sync endpoint enqueues a durable `incremental_reindex` task and returns before initializing Embedding or Qdrant. The worker compares local route hashes with Qdrant metadata, embeds only new or changed routes, deletes removed routes, and records its counts on the task. Repeated requests coalesce while a scan is queued; a request made during a running scan creates one follow-up scan so concurrent edits are not missed.

Explicit full reindex remains available for embedding-model or collection migrations. Normal create, update, delete, feedback, import, and repair operations use route-scoped background synchronization. Diagnostics refresh runs as a separate asynchronous phase after indexing, so it does not delay save or index readiness.

Manual reindex writes Qdrant points in bounded batches and verifies the final point count, route IDs, and route hashes. Incremental reindex rejects an unexpectedly large deletion set according to `MAX_DELETE_RATIO`; an intentional large replacement must use the explicit full-reindex path.

An optional read-only Agent API adapter can merge selected upstream Agents into the same route store. Upstream IDs are retained as `source.source_id`, while local route IDs and `route_key` values remain master-owned. Each pull records a source snapshot, preserves manually overridden fields, and disables records that disappear upstream. Pulling changes only local route state; vector writes remain explicit. Restoring an overridden field follows the normal background synchronization path.
