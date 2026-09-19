# Architecture

Intent Hub has one Flask service, one Vue administration UI, and one shared runtime workspace.

```text
intent-hub-backend/
├── intent_hub/
│   ├── api/
│   ├── core/
│   └── services/
└── data/
    ├── routes.sqlite3
    ├── settings.json
    └── diagnostics_cache.json
```

One component manager creates the encoder, Qdrant client, and route manager. Qdrant and embedding endpoints are complete URLs passed without inferred ports. Management login keys and the external `PREDICT_AUTH_KEY` are separate.

The embedding client supports two explicit wire formats: `qwen` keeps the existing `/get_embeddings` request/response contract, while `tei` sends `{"inputs": [...]}` to the exact configured endpoint and accepts a plain embedding array. The default Free4inno service uses the TEI-compatible `http://embedding.free4inno.com/embed` endpoint. The protocol is never guessed at runtime.

Each synced route also has one Qdrant metadata point containing the complete `RouteConfig` payload. It is marked with `is_route_metadata=true` and remains excluded from ordinary utterance matching and diagnostics. Its vector encodes the intent name and description for the optional LLM fallback. A `description_hash` versions the text format, content and embedding model; legacy zero vectors without that hash are excluded from fallback retrieval. Incremental sync backfills them and reuses unchanged description vectors. Changed routes commit recovery metadata only after sample writes succeed. No-op tasks update local task state without rewriting recovery metadata, so remote task IDs/timestamps describe the last content write. Collection recovery reads these records first and only falls back to aggregating legacy utterance payloads when metadata records are absent.

When ordinary routing yields no eligible match, the optional fallback reuses the query embedding, retrieves eligible intent definitions from the same collection, and invokes the configured LLM with a constrained JSON decision. The model may select one candidate, abstain, or report ambiguity. The service validates candidate IDs and current route hashes; timeouts and invalid responses preserve the default route. Description similarity and model self-reported confidence are not substituted for the existing utterance similarity score. This feature is disabled by default and does not alter successful ordinary matches.

SQLite is the source of truth and Qdrant is a derived index. `repository.py` stores entities, legacy identities, a transactional outbox, tasks and migration metadata. `RouteManager` and `AgentStore` are model adapters over that same repository. Each business write and a unique outbox token commit together; persisting an older task cannot consume a newer mutation's token. A single background worker coalesces queued edits, retries transient failures and checks the entity version before marking it synced. IDs are allocated transactionally. The default database is `routes.sqlite3`; an existing `routes.json` is imported once without rewriting its contents. Explicit migration is recommended before upgrading populated installations.

The normal manual sync endpoint enqueues a durable `incremental_reindex` task and returns before initializing Embedding or Qdrant. Manual and route-scoped tasks share the same delta engine: unchanged committed routes perform no remote writes; changed routes reuse same-model text vectors and batch only missing texts (including descriptions) per route. Threshold-only changes update payloads. The metadata commit marker is invalidated before sample mutation and restored by the final metadata write, enabling retry after partial failure. Repeated requests coalesce while a scan is queued; a request made during a running scan creates one follow-up scan so concurrent edits are not missed.

Explicit full reindex remains available for embedding-model or collection migrations. Normal create, update, delete, feedback, import, and repair operations use route-scoped background synchronization. Diagnostics refresh runs as a separate asynchronous phase after indexing, so it does not delay save or index readiness.

Manual reindex writes Qdrant points in bounded batches and verifies the final point count, route IDs, and route hashes. Ordinary incremental checks read committed route manifests plus the exact collection count; legacy/incomplete manifests or mismatched counts trigger a full payload scan and route reconciliation. Explicit full rebuild retains full payload validation. External point edits that preserve both counts and commit records require an explicit rebuild; manifests assume Intent Hub owns index writes. Incremental reindex rejects an unexpectedly large deletion set according to `MAX_DELETE_RATIO`; an intentional large replacement must use the explicit full-reindex path.

Settings saves compare effective values: identical submissions neither reset components nor enqueue work. Only component-related changes reset lazy dependencies; model/target/embedding-endpoint changes enqueue an incremental check instead of forcing all routes to rebuild. A model replacement must change `EMBEDDING_MODEL_NAME`, even if the endpoint URL remains unchanged. Task records expose `queue_wait_ms` and `execution_ms`; route results include read/plan, embedding, write and total timings. See [incremental sync changes](changes/incremental-sync/README.md) for validation and limits.

An optional read-only Agent API adapter can merge selected upstream Agents into the same route store. Upstream IDs are retained as `source.source_id`, while local route IDs and `route_key` values remain master-owned. Each pull records a source snapshot, preserves manually overridden fields, and disables records that disappear upstream. Pulling commits local state and sync intent; vector writes are performed by the common worker. Restoring an overridden field follows the normal background synchronization path.


The same application exposes `/compat/master/*` and `/compat/bupt/*`. `API_COMPAT_PROFILE` selects root aliases; neither request payloads nor tokens choose a contract. BUPT serializers preserve Agent details and legacy signed IDs. Its completion-style sync API waits on the same durable executor used by the master asynchronous API. Configuration changes supersede queued tasks for a different index target rather than writing to the wrong collection.

Secrets come only from process environment variables, not editable settings or frontend bundles. The unified frontend uses the master namespace and login on both deployment profiles. No proxy credential injection is enabled. Only one sync worker per database is supported; this release does not implement distributed scheduling.

Migration, recovery boundaries and verification evidence: [branch unification](changes/branch-unification/README.md).


## 路由运行时生命周期

组件按配置代隔离并在启动/切换后后台预热；路由持有同代快照，初始化互斥。
Embedding HTTPX 连接池支持并发，查询向量使用实例级 LRU（最多 128 项、文本不超过
4096 字符），批量同步不填充查询缓存；切换模型配置即切换实例并使旧缓存失效。
LLM 由进程内专属事件循环持有可复用的客户端，配置改变后替换，旧调用结束再释放旧
LLM transport。正负例检索并发、过滤顺序和路由阈值不变。
旧组件代为避免打断同步或已有请求，连接在进程退出时统一关闭；频繁切换配置后建议重启
进程回收旧代。详见 [变更和验证](changes/routing-latency/README.md)。


Upstream pulls now use durable `upstream_pull` tasks and reused-connection serial detail fetches for at most 8 Agents, and bounded concurrency (8) for larger pulls. The live list has routing fields but omits detail-only parameters/source data, so it does not replace raw details; verified pageNum/pageSize pagination is consumed. Only lists containing the full detail contract skip individual detail reads. Failed details retain local records. Changes merge against the latest SQLite state inside a transaction, saving only changed rows and enqueuing only effective index changes. Pull timestamps and membership are source-level metadata. A scope change does not disable records from the old scope.

Index equality excludes source snapshots, pull timestamps, raw details and override flags. SQLite remains authoritative for management state and raw details; Qdrant recovery metadata reflects the last index write and is not a current backup of upstream-only changes. Overall route hashes live on metadata points; sample payloads no longer receive a new route hash on description-only edits. Legacy sample hashes remain readable, with metadata hashes taking precedence. See [upstream pull delivery](changes/upstream-pull/README.md).

Upstream matching uses route_key alone across all local source types. Explicit upstream route_key/routeKey takes priority; legacy title-only upstream data derives a normalized key from title. Source IDs are provenance, not entity identity. Duplicate keys in one pull reject the transaction; existing suffix/custom keys are not silently renamed or merged.
