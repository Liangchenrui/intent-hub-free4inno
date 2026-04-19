# Async Route Sync and SSE Status Design

Date: 2026-04-19

## Summary

Intent Hub's current Web flow treats vector sync as a manual operation. Route CRUD updates tenant-local `routes.json`, but Qdrant is refreshed only when the user explicitly triggers `/tenant/reindex` or `/tenant/reindex/sync-route`. This creates a poor product shape for the Web UI:

- users must remember to sync after editing routes
- the test page blocks on a localStorage flag rather than real backend state
- diagnostics mixes route repair, sync, and re-detect into a manual multi-step flow
- large full reindex operations are used as a blunt tool even when only one route changed

This design changes Web sync to an automatic backend-managed model:

- route-affecting writes create async sync tasks instead of asking the UI to call sync APIs directly
- a background worker executes tenant-scoped route sync or full reindex jobs
- the frontend subscribes to tenant-scoped Server-Sent Events (SSE) and renders real sync status
- route-level sync becomes the default path for create, update, delete, and most repair/import actions
- full reindex remains an admin/operator escape hatch for model changes, migrations, or data repair

The source of truth remains tenant-local route configuration files. Qdrant remains a derived index.

## Goals

- Make Web route edits feel immediate: save returns quickly and sync continues in the background.
- Remove the requirement for users to manually trigger sync after normal route edits.
- Treat Qdrant as an eventually consistent derived view of `routes.json`.
- Prefer route-scoped sync over tenant-wide full reindex for normal edits.
- Expose accurate sync state to the UI via SSE rather than local-only heuristics.
- Preserve multi-tenant isolation and prevent conflicting writes against the same tenant collection.
- Keep the first version compatible with the repository's current Flask + file-backed runtime model.

## Non-Goals

- Introducing Redis, Celery, or external queue infrastructure in the first version.
- Replacing the existing sync algorithms in `SyncService`.
- Making CLI or SDK flows real-time in this phase.
- Guaranteeing zero-delay consistency between route save and vector availability.
- Removing manual full reindex APIs entirely.

## Current State

### Backend

- Route CRUD updates tenant-local `routes.json`.
- `SyncService` already supports:
  - `reindex(force_full=False)` for incremental tenant-wide sync
  - `reindex(force_full=True)` for full rebuild
  - `sync_route(route_id)` for route-level delete-and-rebuild
  - `sync_routes(route_ids)` for multi-route sync
- Prediction and diagnostics read from Qdrant, so stale vectors can exist after route edits until a sync endpoint is called.
- There is currently no background task abstraction, no task persistence, and no SSE endpoint.

### Frontend

- The Web UI calls `/tenant/reindex` manually for full sync.
- Diagnostics sometimes calls `/tenant/reindex/sync-route` for targeted route sync.
- Route create, update, delete, import, and many repair operations clear `last_full_reindex` in localStorage rather than triggering automatic sync.
- The test page uses `last_full_reindex` as a proxy for backend readiness.

## Product Behavior

### Normal Save Flow

For route-affecting operations initiated by the Web tenant UI:

1. The backend persists the route change to tenant-local files.
2. The backend creates a sync task in `queued` state.
3. The API response returns immediately with the updated route payload plus sync metadata.
4. A background worker processes the task.
5. The frontend receives SSE events and updates route status in place.

The user sees:

- "Saved successfully"
- a subtle route status such as "Syncing..."
- later, "Synced" or "Sync failed"

The user does not need to click a sync button for ordinary route edits.

### When Route-Level Sync Is Used

Route-level sync is the default for:

- route create
- route update
- route delete
- positive/negative utterance feedback that changes one route
- diagnostics repair flows that update a known set of routes
- import merge when the backend can enumerate the affected route IDs

### When Full Reindex Is Used

Full reindex is reserved for:

- explicit admin/operator action
- embedding model or vector dimension changes
- import replace flows that rewrite the tenant route set wholesale
- recovery from historical index corruption when the affected scope is unknown

## Architecture

## Task Model

Add a tenant-scoped sync task record with the following fields:

- `task_id`
- `tenant_id`
- `kind`: `route_sync` | `full_reindex`
- `route_ids`: list of route IDs, empty for `full_reindex`
- `trigger`
- `status`: `queued` | `running` | `succeeded` | `failed` | `superseded`
- `created_at`
- `started_at`
- `finished_at`
- `error`
- `attempt`
- `max_attempts`

Recommended trigger values:

- `route_create`
- `route_update`
- `route_delete`
- `positive_feedback`
- `negative_feedback`
- `diagnostics_repair`
- `import_merge`
- `import_replace`
- `admin_full_reindex`

## Task Persistence

Store task state in the tenant workspace instead of memory-only structures so the UI can inspect status after refresh and failures are not invisible.

New tenant-local file:

```text
intent-hub-backend/data/tenants/<tenant_id>/sync_tasks.json
```

The first version may keep an in-memory scheduler index for runtime convenience, but the task source of truth should be the file-backed task list.

Persistence requirements:

- task creation must be durable before the API reports success
- task status transitions must be persisted before emitting SSE events
- restart recovery may resume `queued` tasks and treat stale `running` tasks as `queued` again

## Scheduler and Worker

Implement an in-process background scheduler inside the backend runtime.

Constraints:

- tasks must execute serially per tenant
- different tenants may execute independently
- `full_reindex` has higher priority than `route_sync`
- the worker must never run route-level and tenant-level sync concurrently for the same tenant

Recommended first-version structure:

- `SyncTaskRepository`
  - load/save/list/update task records from `sync_tasks.json`
- `SyncTaskService`
  - enqueue tasks
  - merge or supersede redundant tasks
  - expose task snapshots for API and SSE
- `TenantSyncScheduler`
  - maintain one execution lane per tenant
  - pick the next runnable task
  - invoke existing `SyncService`
- `SyncEventBroker`
  - fan out task status events to connected SSE clients

## Task Merge Rules

The queue must avoid unbounded growth when the same route is edited repeatedly.

Rules:

1. If a `full_reindex` is `queued` or `running` for a tenant, newly created `route_sync` tasks become `superseded`.
2. If a matching `route_sync` task is still `queued`, merge route IDs into the newest queued task instead of appending another near-duplicate task.
3. If a route is edited again while an older task is `running`, enqueue one follow-up `route_sync` task containing the latest affected route IDs.
4. Deleting a route does not require full reindex. The route sync handler should remove that route's positive and negative vectors and clean related diagnostics cache.
5. `import_replace` may directly enqueue `full_reindex` rather than many route tasks.

These rules keep behavior correct without requiring deep transactional complexity.

## API Changes

### Route-Affecting Write APIs

Existing tenant APIs that mutate route state should enqueue sync automatically and include sync metadata in their responses.

Affected API groups include:

- `/tenant/routes`
- `/tenant/routes/<id>`
- feedback endpoints that change route utterances or negative samples
- import endpoints
- diagnostics apply/repair endpoints that mutate routes

Response additions:

- `sync_task_id`
- `sync_status`
- `sync_kind`

The write API remains synchronous for config persistence and validation only. It must not wait for embedding generation or Qdrant writes.

### Task Inspection API

Add read APIs so the frontend can bootstrap status after page load:

- `GET /tenant/sync-tasks`
- optional query params:
  - `status`
  - `limit`
  - `route_id`

Response use cases:

- hydrate current task state after refresh
- show recent failures
- support retry UX

### Retry API

Add a retry endpoint:

- `POST /tenant/sync-tasks/<task_id>/retry`

Rules:

- only `failed` tasks may be retried directly
- retry creates a new task rather than mutating historical task identity

### Manual Full Reindex API

Keep `/tenant/reindex` and existing admin/manual paths, but redefine their intended use:

- admin/operator escape hatch
- not part of routine Web editing flow

## SSE Design

Add a tenant-scoped SSE endpoint:

- `GET /tenant/sync-events`

Characteristics:

- authenticated with the same tenant access credentials as other `/tenant/*` APIs
- response type `text/event-stream`
- emits task status updates for the current tenant
- supports reconnect by sending current snapshots or recent task events after connection opens

Recommended event payload:

```json
{
  "type": "sync_task_updated",
  "task_id": "task_123",
  "tenant_id": "tenant_a",
  "kind": "route_sync",
  "route_ids": [12, 15],
  "trigger": "route_update",
  "status": "running",
  "message": "Syncing 2 routes",
  "error": null,
  "created_at": "2026-04-19T10:00:00Z",
  "started_at": "2026-04-19T10:00:02Z",
  "finished_at": null
}
```

Connection semantics:

- one SSE connection per active tenant session is sufficient
- the server should send keepalive comments periodically
- the frontend should reconnect with backoff on disconnect

## Frontend Design

## Route Status UX

Replace the current "manual sync required" mental model with route-level background status.

UI principles:

- save success and sync progress are separate states
- route rows may show `queued`, `running`, `failed`, or short-lived `succeeded`
- successful steady state should be visually quiet
- failures must remain visible and actionable

Recommended user-facing behavior:

- after save: toast "Saved successfully. Syncing in background."
- while running: lightweight badge or row status
- on success: subtle completion toast and then quiet stable UI
- on failure: explicit error badge plus retry action

## Page-Level Behavior

### Route List

- saving a route should not clear a localStorage flag
- list rows should update from SSE or task bootstrap state
- bulk import should show aggregated background progress rather than one toast per route

### Test Page

Remove dependence on `last_full_reindex`.

New behavior:

- if the tenant has active `queued` or `running` sync tasks, show a banner that results may lag behind the latest edits
- do not hard-block testing in the default UX
- if strict freshness is required later, that should be a separate explicit mode

### Diagnostics

Repair and merge flows should treat sync as a background phase:

- save repair changes
- enqueue affected sync task(s)
- wait for success events
- only then re-run overlap analysis automatically

If sync fails:

- keep the saved route changes
- show that diagnostics results were not refreshed because vector sync failed

## Failure Handling

## Save vs Queue Atomicity

The most important correctness boundary is: route persistence and task creation must succeed together.

Because the repository uses file-backed storage rather than a database transaction, the implementation must explicitly guard against partial success.

Required behavior:

- if route persistence fails, return an error and create no task
- if task persistence fails after route persistence, return an error and roll back the route file write if practical
- if true rollback is too risky in the first version, the API must at minimum surface a hard failure and record a compensating recovery item that can be detected and repaired

The implementation plan should prefer a repository abstraction that writes both route file and task file under one service boundary rather than scattering file writes across APIs.

## Retry Policy

Classify failures into two buckets.

Retryable:

- transient embedding service failure
- Qdrant timeout
- network instability

Non-retryable:

- invalid route data
- missing route after a superseding edit
- collection dimension mismatch

Recommended first-version policy:

- automatic retry up to 3 attempts with backoff for retryable failures
- then mark `failed`
- manual retry from the UI or API creates a new task

## Deleted Route Failures

When a route is deleted from the list, its row disappears before vector cleanup is guaranteed.

The UI therefore needs a tenant-level failure center, not only row-local errors.

Minimal UX:

- top-level notification area for failed sync tasks
- ability to inspect failed task details and retry

## Testing Strategy

Backend tests:

- task enqueue on route create/update/delete
- task merge and supersede rules
- per-tenant serial execution
- SSE event emission on each status transition
- restart recovery for queued/running tasks
- retry behavior and failure persistence
- write-path correctness when task persistence fails

Frontend tests:

- route list reacts to SSE task updates
- test page uses backend task state rather than localStorage
- diagnostics waits for sync success before rerunning detection
- failed task UX remains visible after refresh

Integration tests:

- route edit -> task queued -> task running -> task succeeded -> prediction reflects new vectors
- route delete -> route removed -> vector cleanup task succeeds
- import replace -> full reindex task supersedes route tasks

## Migration Strategy

Phase 1:

- introduce backend task repository, scheduler, and SSE endpoint
- auto-enqueue from route CRUD and route feedback flows
- add frontend SSE client and route list status rendering

Phase 2:

- migrate test page away from localStorage readiness checks
- update diagnostics repair and merge flows to wait on background sync events

Phase 3:

- refine admin/operator tooling for recent failures, retries, and manual full reindex

## Open Design Choices Resolved

- Notification transport: SSE, not polling or WebSocket
- Default sync granularity: route-level where affected scope is known
- User experience: save returns immediately, sync continues in background
- Full reindex: explicit operator path, not default Web behavior

## Risks

- In-process scheduling will not survive multi-process deployment as robustly as an external queue.
- File-backed task persistence adds concurrency risk if multiple backend processes write the same tenant task file.
- SSE adds connection lifecycle complexity in Flask deployments behind proxies.

These are acceptable for the first version because the current repository already uses file-backed tenant state and single-runtime assumptions in other areas. If deployment requirements expand later, task repository and scheduler boundaries should allow replacement with a more durable queue backend.
