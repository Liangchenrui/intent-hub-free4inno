# Client-Side Skill Scan Design

Date: 2026-04-17

## Summary

Intent Hub's current skill scan flow assumes `SkillSourceRecord.path` points to a directory visible to the backend host. That assumption breaks for the actual product shape: users interact with a remotely deployed backend but expect skill scan to operate on their own local directories.

This design changes skill scan to a client-side discovery model:

- CLI and Python SDK scan local directories on the user's machine and upload discovered `SKILL.md` documents to the backend.
- Web tenant pages allow the user to choose a local directory in the browser, recursively read matching `SKILL.md` files, and upload the discovered skills to the backend.
- Backend `SkillSourceRecord` stops representing a backend-readable filesystem root and instead represents a logical source slot used for UX, indexing, and repeat uploads.

The backend remains responsible for draft generation, apply mode, stale detection, and tenant-local storage of scan results.

## Goals

- Make skill scan semantics correct for remote backend deployments.
- Support local path input for CLI and Python SDK.
- Support browser-based local directory selection for the Web tenant UI.
- Preserve the existing source list concept, but reinterpret it as a logical source rather than a server-side directory pointer.
- Keep one backend ingestion pipeline for CLI, SDK, and Web uploads.
- Preserve stale detection, draft generation, and optional apply mode.

## Non-Goals

- Building a native desktop helper or local agent process.
- Supporting true one-click browser re-scan without user directory re-selection.
- Supporting upload of arbitrary non-`SKILL.md` files.
- Preserving backward compatibility for backend-side directory scanning as an active feature.

## User Experience

### CLI

The CLI must support a local scan command that accepts a user-local path:

```bash
intent-hub skills scan --source-path D:/skills
intent-hub skills scan --source-path ./skills --source-label "My Local Skills"
intent-hub skills scan --source-id src_001 --source-path ./skills
```

Behavior:

- `--source-path` accepts absolute or relative paths.
- Relative paths are resolved against the current working directory.
- The CLI scans `<root>/**/SKILL.md`, normalizes each file into a logical skill item, and uploads the skill set to the backend.
- If `--source-id` is omitted, the backend creates a new logical source record using the provided label or a derived label.
- If `--source-id` is provided, the upload updates that existing logical source.

### Python SDK

The SDK must expose a high-level method that mirrors CLI behavior:

```python
client.skills_scan_local(
    source_path="./skills",
    source_label="My Local Skills",
    source_id=None,
)
```

Behavior:

- Local filesystem access happens in the SDK process, not in the backend.
- The SDK serializes discovered skills and posts them to the backend.

### Web Tenant UI

The tenant skill source page must support selecting a local directory from the browser.

Behavior:

- The create-source dialog supports a logical source label instead of a backend path.
- The page includes a "Choose Local Directory" action.
- Browser selection reads matching `SKILL.md` files under the chosen directory and previews:
  - source label
  - selected folder name
  - discovered skill count
  - skipped file count
- Upload is explicit. The user reviews the selection and confirms upload.
- The resulting source remains in the source list as a logical source record.
- Re-scan in Web means selecting a local directory again and uploading to an existing source. The browser cannot silently re-read the previous directory later.

## Product Semantics

### Source Record

`SkillSourceRecord` changes from "backend filesystem root" to "logical source slot".

Required fields:

- `source_id`
- `source_label`
- `enabled`
- `sync_mode`

Optional metadata fields:

- `source_kind`: `uploaded`
- `last_uploaded_at`
- `last_uploaded_count`
- `client_path_hint`

Rules:

- `client_path_hint` is informational only and is never used by the backend for filesystem access.
- The backend must not attempt to read any path from `SkillSourceRecord`.
- Existing `path` storage must be migrated or deprecated cleanly.

### Skill Identity

Backend indexing must no longer use backend absolute paths as the primary identity key.

Stable identity key:

- `source_id + "::" + relative_path`

Where `relative_path` is the client-side relative path from the selected local root to `SKILL.md`, normalized to forward slashes.

This allows:

- stable updates for unchanged local tree structure
- stale detection based on uploaded set membership
- no dependency on backend-visible paths

## Data Model

### Uploaded Skill Item

Each uploaded skill item contains:

- `skill_name`
- `relative_path`
- `content`
- `content_hash`

Optional metadata:

- `client_mtime`
- `client_path_hint`

Validation:

- `relative_path` must end with `/SKILL.md` or equal `SKILL.md`
- `content` must be non-empty UTF-8 text
- `content_hash` must match server-recomputed hash if provided
- duplicate `relative_path` values within the same request are rejected

### Skills Index

`skills_index.json` entries must evolve to include:

- `source_id`
- `source_label`
- `skill_key`
- `skill_name`
- `relative_path`
- `client_path_hint`
- `skill_hash`
- `json_hash`
- `draft_file`
- `status`
- `last_scanned_at`
- `last_synced_at`
- `route_id`

Entries must no longer require `skill_path` to be a backend absolute path.

For backward compatibility, old entries may still contain `skill_path`, but newly written items should use the new fields and treat `skill_path` as deprecated.

## API Design

### Create Source

`POST /tenant/skill-sources`

Request:

```json
{
  "source_label": "My Local Skills",
  "sync_mode": "apply",
  "enabled": true,
  "client_path_hint": "D:/skills"
}
```

Response returns the logical source record.

Notes:

- `path` is removed from the required UX contract.
- If a legacy client sends `path`, the backend may map it into `client_path_hint` during the transition period.

### Upload Scan

Primary ingestion endpoint:

`POST /tenant/skill-sources/scan`

Request:

```json
{
  "source_id": "src_001",
  "source_label": "My Local Skills",
  "client_path_hint": "D:/skills",
  "skills": [
    {
      "skill_name": "wiki_builder",
      "relative_path": "wiki_builder/SKILL.md",
      "content": "# Wiki Builder\nbuild wiki",
      "content_hash": "..."
    }
  ]
}
```

Behavior:

- If `source_id` is omitted, the backend creates a new logical source record before processing.
- If `source_id` is provided, the backend validates that the source exists for the current tenant.
- The backend scans only the uploaded `skills` payload.
- Stale detection compares previous indexed items for that `source_id` with the uploaded skill keys in this request.
- `sync_mode=apply` still applies generated drafts to routes as today.

Response:

- `source_id`
- `discovered`
- `uploaded`
- `updated`
- `stale`
- `applied`
- `skipped`
- `errors`

### Error Cases

The endpoint must return clear validation errors for:

- no `source_id` and no `source_label`
- empty `skills`
- malformed `relative_path`
- oversized request body
- duplicate skill keys in one upload
- invalid `content_hash`

## Backend Architecture

### Service Split

Current `SkillScanService` is tightly coupled to backend-local directory reads. Refactor into two responsibilities:

1. client upload ingestion service
2. index and draft reconciliation service

Recommended shape:

- `LocalSkillCollector` in CLI/SDK
- `UploadedSkillScanService` in backend

The backend service should accept normalized uploaded items rather than a local root path.

### Processing Flow

1. Validate or create logical source.
2. Normalize uploaded items.
3. Load existing `skills_index.json`.
4. For each uploaded item:
   - compute skill key
   - compute or verify skill hash
   - compare against existing item
   - regenerate draft when content changed or item is new
   - optionally apply draft
5. Mark previously indexed items under the same `source_id` as stale if absent from this upload.
6. Persist updated `skills_index.json`.

### Draft File Layout

Current draft file layout under tenant imports may stay:

- `imports/skills/<source_id>/<skill_name>.json`

To avoid collisions when multiple uploaded skills share the same directory name, draft filenames should become deterministic from the relative path, for example:

- `imports/skills/<source_id>/<slugified-relative-path>.json`

This is required because backend absolute paths are no longer unique and sibling structures may repeat names.

## Web Frontend Design

### Directory Selection

Use browser directory selection via file input with directory mode support.

Requirements:

- user selects a folder
- frontend receives recursive file list
- frontend filters to files named `SKILL.md`
- frontend derives `relative_path` from browser-provided relative path
- frontend reads file content asynchronously before upload

### UI Changes

Skill source page changes:

- replace `Path` field in create dialog with `Source Label`
- add optional display-only field for last selected local directory hint
- add "Choose Local Directory" button
- add upload preview state before sending
- keep source list table, but replace `path` column with `source_label` and status metadata

### Browser Limitations

The UI must acknowledge browser constraints:

- previous local directory cannot be silently reopened
- re-scan requires user re-selection
- absolute local filesystem path may be unavailable or partially redacted by the browser

## CLI and SDK Design

### Local File Discovery

Discovery rule:

- recursively find files named `SKILL.md`
- derive `skill_name` from the immediate parent directory name
- derive `relative_path` relative to the provided root

Validation:

- reject non-existent root
- reject file roots when a directory is expected
- skip unreadable files and report them
- treat empty `SKILL.md` as an error item, not a valid skill

### Output

CLI response should show:

- source id
- discovered count
- uploaded count
- updated count
- stale count
- applied count
- skipped count
- any local read errors before upload

## Migration Plan

### Stored Source Records

Existing source records likely contain `path`.

Migration approach:

- keep reading legacy `path` fields
- map them into `client_path_hint` for display only
- introduce `source_label`
- default `source_label` to basename of legacy path or `source_id`
- stop using `path` as executable meaning anywhere in the backend

### Existing Skills Index

Existing `skills_index.json` entries use `skill_path`.

Migration approach:

- preserve old records on read
- when an uploaded scan for a source runs, rewrite matching entries into the new schema
- stale legacy entries under the same source are rewritten with new status fields on next save

### Compatibility Window

During transition:

- old clients calling scan without uploaded `skills` should receive a descriptive 400 error
- docs must explicitly state that local scan now happens in CLI/SDK/Web client, not on the backend

## Testing Strategy

### Backend Tests

Add tests for:

- creating a logical source without backend path semantics
- uploaded scan generates drafts from uploaded items
- changed uploaded content updates only affected entries
- missing previously uploaded items become stale
- apply mode still sets `route_id` and sync status
- duplicate relative paths are rejected
- invalid content hash is rejected
- deterministic draft filenames avoid collisions

### CLI Tests

Add tests for:

- relative path resolution
- recursive discovery of local `SKILL.md`
- payload serialization sent to backend
- source creation and source update modes
- local read failures surfaced cleanly

### Frontend Tests

Add tests for:

- directory file list filtering
- relative path extraction
- preview summary rendering
- upload request shape
- validation and error messaging

## Risks

### Request Size

Uploading many `SKILL.md` files in one request may create large payloads.

Mitigations:

- request size limit
- client-side count and total-bytes checks
- optional future chunked upload if needed

### Draft Filename Collisions

Using only `skill_name` for filenames is no longer safe.

Mitigation:

- base filenames on normalized relative paths

### Misleading Source Metadata

Users may assume stored local directory hints can be re-opened by the backend.

Mitigation:

- UI copy must explicitly say local directories are selected and read on the client side

## Open Decisions Resolved

- The system keeps the source list concept.
- Source records are logical metadata, not backend directory mounts.
- Web re-scan requires user re-selecting a local directory.
- CLI and SDK are the canonical path-based entrypoints for local filesystem scanning.
- Backend directory scanning is removed as an active behavior.

## Recommended Implementation Order

1. Introduce new API schema and backend upload ingestion service.
2. Update backend index and draft naming logic.
3. Add CLI local collector and SDK helper.
4. Update Web tenant skill source page to upload local directory contents.
5. Migrate docs and user-facing terminology.
6. Remove remaining backend path-scan behavior.
