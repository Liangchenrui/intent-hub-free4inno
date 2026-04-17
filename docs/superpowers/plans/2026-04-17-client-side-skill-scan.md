# Client-Side Skill Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace backend filesystem-based skill scanning with a client-side upload flow that works from CLI, Python SDK, and the Web tenant UI.

**Architecture:** The backend stops reading `SkillSourceRecord.path` as an executable directory and instead ingests uploaded `SKILL.md` payloads keyed by `source_id + relative_path`. CLI/SDK add a local collector that reads the user's filesystem and uploads normalized skill items, while the Web UI uses browser directory selection to read local files and post the same payload shape.

**Tech Stack:** Flask, Pydantic, Python requests SDK, argparse CLI, Vue 3, TypeScript, Element Plus, pytest

---

## File Structure

### Backend

- Modify: `intent-hub-backend/intent_hub/platform/models.py`
  - Add logical-source fields to `SkillSourceRecord`.
- Modify: `intent-hub-backend/intent_hub/api/tenant.py`
  - Accept logical source creation and uploaded scan payloads.
- Modify: `intent-hub-backend/intent_hub/services/skill_scan_service.py`
  - Replace backend directory traversal with uploaded-item ingestion.
- Modify: `intent-hub-backend/intent_hub/platform/registry.py`
  - Preserve backward compatibility while creating logical source records.
- Modify: `intent-hub-backend/tests/test_skill_scan_service.py`
  - Rework tests around uploaded payloads rather than backend-local roots.
- Modify: `intent-hub-backend/tests/test_tenant_skill_api.py`
  - Cover create-source and uploaded-scan API behavior.

### CLI and SDK

- Modify: `intent-hub-cli/intent_hub_cli/client.py`
  - Add uploaded scan API method.
- Modify: `intent-hub-cli/intent_hub_cli/cli.py`
  - Add local-path-based `skills scan` arguments and output.
- Create: `intent-hub-cli/intent_hub_cli/skill_collector.py`
  - Local recursive `SKILL.md` discovery and payload normalization.
- Modify: `intent-hub-cli/tests/test_client.py`
  - Validate uploaded scan request shape.
- Modify: `intent-hub-cli/tests/test_cli.py`
  - Validate CLI path handling and payload upload behavior.

### Frontend

- Modify: `intent-hub-frontend/src/api/index.ts`
  - Update skill source types and scan request contract.
- Modify: `intent-hub-frontend/src/views/tenant/SkillSources.vue`
  - Replace backend-path UX with logical-source plus local directory upload UX.

### Documentation

- Modify: `USER_GUIDE.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `intent-hub-cli/README.md`
  - Document that scan happens on the client and that Web re-scan requires user re-selection.

## Task 1: Redefine Backend Skill Source Model

**Files:**
- Modify: `intent-hub-backend/intent_hub/platform/models.py`
- Modify: `intent-hub-backend/tests/test_tenant_registry.py`
- Test: `intent-hub-backend/tests/test_tenant_registry.py`

- [ ] **Step 1: Write the failing model and registry tests**

```python
def test_skill_source_record_supports_logical_source_fields():
    source = SkillSourceRecord(
        source_id="src_001",
        source_label="My Local Skills",
        enabled=True,
        sync_mode="apply",
        client_path_hint="D:/skills",
    )

    assert source.source_label == "My Local Skills"
    assert source.client_path_hint == "D:/skills"


def test_registry_create_skill_source_defaults_label_from_path_when_missing(test_dir):
    registry = TenantRegistry(test_dir / "platform" / "tenants.json")
    registry.save_tenants(
        [
            TenantRecord(
                tenant_id="team_alpha",
                name="Team Alpha",
                status="active",
                qdrant_collection="intent_hub_team_alpha",
                access_codes=[],
                skill_sources=[],
            )
        ]
    )

    _, source = registry.create_skill_source(
        tenant_id="team_alpha",
        path="D:/skills/default",
        sync_mode="apply",
        enabled=True,
    )

    assert source.source_label == "default"
    assert source.client_path_hint == "D:/skills/default"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-backend\tests\test_tenant_registry.py -q`
Expected: FAIL because `SkillSourceRecord` lacks `source_label` and `client_path_hint`, and registry creation does not populate them.

- [ ] **Step 3: Implement minimal model and registry changes**

```python
class SkillSourceRecord(BaseModel):
    source_id: str = Field(..., description="Stable source ID")
    source_label: str = Field(..., description="Human-readable source label")
    enabled: bool = Field(default=True, description="Whether source is active")
    sync_mode: Literal["scan", "apply"] = Field(default="scan", description="Skill source sync mode")
    client_path_hint: Optional[str] = Field(default=None, description="Client-local directory hint")
```

```python
def create_skill_source(self, tenant_id: str, path: str, sync_mode: str = "apply", enabled: bool = True, source_label: str | None = None):
    hint = (path or "").strip() or None
    label = (source_label or "").strip() or (Path(hint).name if hint else None) or f"source-{source_id}"
    source = SkillSourceRecord(
        source_id=source_id,
        source_label=label,
        enabled=enabled,
        sync_mode=sync_mode,
        client_path_hint=hint,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-backend\tests\test_tenant_registry.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-backend/intent_hub/platform/models.py intent-hub-backend/intent_hub/platform/registry.py intent-hub-backend/tests/test_tenant_registry.py
git commit -m "feat: redefine skill sources as logical records"
```

## Task 2: Convert Backend Scan Service to Uploaded Skill Ingestion

**Files:**
- Modify: `intent-hub-backend/intent_hub/services/skill_scan_service.py`
- Modify: `intent-hub-backend/tests/test_skill_scan_service.py`
- Test: `intent-hub-backend/tests/test_skill_scan_service.py`

- [ ] **Step 1: Write failing service tests for uploaded payloads**

```python
def test_skill_scan_ingests_uploaded_skills_and_generates_drafts(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)

    result = service.scan_uploaded_source(
        source=SkillSourceRecord(
            source_id="src_001",
            source_label="My Local Skills",
            enabled=True,
            sync_mode="scan",
            client_path_hint="D:/skills",
        ),
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    assert result["discovered"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert index["items"][0]["skill_key"] == "src_001::wiki_builder/SKILL.md"


def test_skill_scan_marks_missing_uploaded_skills_as_stale(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    source = SkillSourceRecord(
        source_id="src_001",
        source_label="My Local Skills",
        enabled=True,
        sync_mode="scan",
        client_path_hint="D:/skills",
    )

    service.scan_uploaded_source(
        source=source,
        uploaded_skills=[{"skill_name": "wiki_builder", "relative_path": "wiki_builder/SKILL.md", "content": "# Wiki Builder\nbuild wiki"}],
    )
    result = service.scan_uploaded_source(source=source, uploaded_skills=[])

    assert result["stale"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-backend\tests\test_skill_scan_service.py -q`
Expected: FAIL because `scan_uploaded_source` does not exist and index entries still depend on backend paths.

- [ ] **Step 3: Implement minimal uploaded ingestion service**

```python
def scan_uploaded_source(self, source: SkillSourceRecord, uploaded_skills: list[dict]) -> dict:
    index = self._load_index()
    active_items: dict[str, dict] = {}
    discovered = len(uploaded_skills)
    updated = 0
    applied = 0
    stale = 0
    now = self._utc_now()

    for payload in uploaded_skills:
        relative_path = self._normalize_relative_path(payload["relative_path"])
        content = payload["content"]
        key = f"{source.source_id}::{relative_path}"
        existing = index.get(key)
        item = dict(existing or {})
        item["source_id"] = source.source_id
        item["source_label"] = source.source_label
        item["skill_key"] = key
        item["skill_name"] = payload["skill_name"]
        item["relative_path"] = relative_path
        item["client_path_hint"] = payload.get("client_path_hint") or source.client_path_hint
        item["skill_hash"] = self._hash_text(content)
        item["last_scanned_at"] = now
        item["status"] = "pending"
        if existing is None or existing.get("skill_hash") != item["skill_hash"]:
            draft_payload = self._generate_draft(Path(relative_path), content)
            draft_path = self._draft_file_path(source.source_id, relative_path)
            draft_path.parent.mkdir(parents=True, exist_ok=True)
            draft_path.write_text(json.dumps(draft_payload, ensure_ascii=False, indent=2), encoding="utf-8")
            item["draft_file"] = str(draft_path)
            updated += 1
        active_items[key] = item

    for key, item in index.items():
        if item.get("source_id") == source.source_id and key not in active_items:
            stale_item = dict(item)
            stale_item["status"] = "stale"
            active_items[key] = stale_item
            stale += 1
        elif key not in active_items:
            active_items[key] = item

    self._save_index({"items": list(active_items.values())})
    return {"discovered": discovered, "uploaded": discovered, "updated": updated, "stale": stale, "applied": applied, "skipped": 0, "errors": []}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-backend\tests\test_skill_scan_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-backend/intent_hub/services/skill_scan_service.py intent-hub-backend/tests/test_skill_scan_service.py
git commit -m "feat: ingest uploaded skills in scan service"
```

## Task 3: Add Backend Validation, Apply Mode, and Collision-Safe Draft Naming

**Files:**
- Modify: `intent-hub-backend/intent_hub/services/skill_scan_service.py`
- Modify: `intent-hub-backend/tests/test_skill_scan_service.py`
- Test: `intent-hub-backend/tests/test_skill_scan_service.py`

- [ ] **Step 1: Write failing tests for validation and apply mode**

```python
def test_skill_scan_rejects_duplicate_relative_paths(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    source = SkillSourceRecord(source_id="src_001", source_label="My Local Skills", enabled=True, sync_mode="scan")

    with pytest.raises(ValueError, match="duplicate relative_path"):
        service.scan_uploaded_source(
            source=source,
            uploaded_skills=[
                {"skill_name": "a", "relative_path": "dup/SKILL.md", "content": "# A"},
                {"skill_name": "b", "relative_path": "dup/SKILL.md", "content": "# B"},
            ],
        )


def test_skill_scan_apply_mode_sets_route_id_and_synced_status(test_dir):
    context = make_context(test_dir)
    source = SkillSourceRecord(source_id="src_001", source_label="My Local Skills", enabled=True, sync_mode="apply")

    def applier(draft_payload, source, skill_file):
        return {"route_id": 42}

    service = SkillScanService(context, draft_generator=draft_generator, draft_applier=applier)
    result = service.scan_uploaded_source(
        source=source,
        uploaded_skills=[{"skill_name": "wiki_builder", "relative_path": "wiki_builder/SKILL.md", "content": "# Wiki Builder\nbuild wiki"}],
    )

    assert result["applied"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert index["items"][0]["route_id"] == 42
    assert index["items"][0]["status"] == "synced"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-backend\tests\test_skill_scan_service.py -q`
Expected: FAIL because duplicate validation and apply-mode wiring are incomplete.

- [ ] **Step 3: Implement validation and deterministic draft filenames**

```python
def _normalize_relative_path(self, relative_path: str) -> str:
    normalized = relative_path.replace("\\", "/").strip("/")
    if not normalized or not normalized.endswith("SKILL.md"):
        raise ValueError("relative_path must point to SKILL.md")
    return normalized


def _draft_file_path(self, source_id: str, relative_path: str) -> Path:
    slug = relative_path.replace("/", "__").replace("\\", "__").replace(".md", "").replace(".", "_")
    return self.tenant_context.imports_dir / "skills" / source_id / f"{slug}.json"
```

```python
seen_paths: set[str] = set()
for payload in uploaded_skills:
    relative_path = self._normalize_relative_path(payload["relative_path"])
    if relative_path in seen_paths:
        raise ValueError(f"duplicate relative_path: {relative_path}")
    seen_paths.add(relative_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-backend\tests\test_skill_scan_service.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-backend/intent_hub/services/skill_scan_service.py intent-hub-backend/tests/test_skill_scan_service.py
git commit -m "feat: validate uploaded skills and preserve apply mode"
```

## Task 4: Update Tenant Skill Source API to Accept Uploaded Scans

**Files:**
- Modify: `intent-hub-backend/intent_hub/api/tenant.py`
- Modify: `intent-hub-backend/tests/test_tenant_skill_api.py`
- Test: `intent-hub-backend/tests/test_tenant_skill_api.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_tenant_skill_source_create_accepts_source_label(test_dir, monkeypatch):
    client = make_tenant_client(test_dir, monkeypatch)

    response = client.post(
        "/tenant/skill-sources",
        json={"source_label": "My Local Skills", "sync_mode": "apply", "enabled": True, "client_path_hint": "D:/skills"},
    )

    assert response.status_code == 201
    assert response.get_json()["item"]["source_label"] == "My Local Skills"


def test_tenant_skill_scan_accepts_uploaded_skills(test_dir, monkeypatch):
    client = make_tenant_client(test_dir, monkeypatch)
    create_response = client.post("/tenant/skill-sources", json={"source_label": "My Local Skills", "sync_mode": "apply", "enabled": True})
    source_id = create_response.get_json()["item"]["source_id"]

    response = client.post(
        "/tenant/skill-sources/scan",
        json={
            "source_id": source_id,
            "skills": [{"skill_name": "wiki_builder", "relative_path": "wiki_builder/SKILL.md", "content": "# Wiki Builder\nbuild wiki"}],
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source_id"] == source_id
    assert payload["discovered"] == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-backend\tests\test_tenant_skill_api.py -q`
Expected: FAIL because API still expects `path` and still calls backend-local scan.

- [ ] **Step 3: Implement minimal API request handling**

```python
def create_skill_source():
    data = request.get_json() or {}
    _, source = get_tenant_registry().create_skill_source(
        tenant_id=g.tenant_context.tenant_id,
        path=data.get("path", "") or data.get("client_path_hint", ""),
        source_label=data.get("source_label"),
        sync_mode=data.get("sync_mode", "apply"),
        enabled=data.get("enabled", True),
    )
    return jsonify({"item": source.model_dump(mode="json")}), 201


def scan_skill_sources():
    data = request.get_json() or {}
    skills = data.get("skills")
    if not isinstance(skills, list):
        raise ValueError("skills is required")
    tenant = get_tenant_registry().get_tenant(g.tenant_context.tenant_id)
    source_id = data.get("source_id")
    source = next((item for item in tenant.skill_sources if item.source_id == source_id), None) if source_id else None
    if source is None:
        _, source = get_tenant_registry().create_skill_source(
            tenant_id=g.tenant_context.tenant_id,
            path=data.get("client_path_hint", ""),
            source_label=data.get("source_label"),
            sync_mode=data.get("sync_mode", "apply"),
            enabled=True,
        )
    scan_service = SkillScanService(...)
    result = scan_service.scan_uploaded_source(source=source, uploaded_skills=skills)
    return jsonify({"source_id": source.source_id, **result}), 200
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-backend\tests\test_tenant_skill_api.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-backend/intent_hub/api/tenant.py intent-hub-backend/tests/test_tenant_skill_api.py
git commit -m "feat: accept uploaded skill scans in tenant api"
```

## Task 5: Add CLI and SDK Local Skill Collection

**Files:**
- Create: `intent-hub-cli/intent_hub_cli/skill_collector.py`
- Modify: `intent-hub-cli/intent_hub_cli/client.py`
- Modify: `intent-hub-cli/intent_hub_cli/cli.py`
- Modify: `intent-hub-cli/tests/test_client.py`
- Modify: `intent-hub-cli/tests/test_cli.py`
- Test: `intent-hub-cli/tests/test_client.py`
- Test: `intent-hub-cli/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI and SDK tests**

```python
def test_client_skills_scan_uploaded_posts_expected_payload():
    session = DummySession()
    client = IntentHubClient(endpoint="https://api.example.com", access_code="token", session=session)

    client.skills_scan_uploaded(
        source_id="src_001",
        source_label="My Local Skills",
        client_path_hint="D:/skills",
        skills=[{"skill_name": "wiki_builder", "relative_path": "wiki_builder/SKILL.md", "content": "# Wiki Builder\nbuild wiki"}],
    )

    assert session.calls[0]["url"] == "https://api.example.com/tenant/skill-sources/scan"
    assert session.calls[0]["json"]["skills"][0]["relative_path"] == "wiki_builder/SKILL.md"


def test_cli_skills_scan_collects_local_directory(tmp_path, monkeypatch, capsys):
    skills_root = tmp_path / "skills"
    (skills_root / "wiki_builder").mkdir(parents=True, exist_ok=True)
    (skills_root / "wiki_builder" / "SKILL.md").write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")

    class DummyClient:
        def skills_scan_uploaded(self, **kwargs):
            return {"source_id": "src_001", "discovered": len(kwargs["skills"]), "uploaded": len(kwargs["skills"]), "updated": 1, "stale": 0, "applied": 1, "skipped": 0, "errors": []}

    monkeypatch.setattr(cli, "_client_from_config", lambda: DummyClient())
    exit_code = cli.main(["skills", "scan", "--source-path", str(skills_root), "--source-label", "My Local Skills"])

    assert exit_code == 0
    assert '"discovered": 1' in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-cli\tests\test_client.py .\intent-hub-cli\tests\test_cli.py -q`
Expected: FAIL because client uploader, collector, and CLI flags do not exist.

- [ ] **Step 3: Implement collector, client uploader, and CLI flags**

```python
def collect_skills(source_path: str) -> tuple[str, list[dict], list[str]]:
    root = Path(source_path).resolve()
    if not root.exists():
        raise ValueError(f"source path not found: {source_path}")
    if not root.is_dir():
        raise ValueError(f"source path must be a directory: {source_path}")

    skills = []
    errors = []
    for skill_file in sorted(root.rglob("SKILL.md")):
        try:
            content = skill_file.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"{skill_file}: {exc}")
            continue
        if not content.strip():
            errors.append(f"{skill_file}: empty SKILL.md")
            continue
        skills.append(
            {
                "skill_name": skill_file.parent.name,
                "relative_path": skill_file.relative_to(root).as_posix(),
                "content": content,
            }
        )
    return str(root), skills, errors
```

```python
def skills_scan_uploaded(self, source_id: str | None, source_label: str | None, client_path_hint: str | None, skills: list[dict]) -> dict[str, Any]:
    payload = {"source_id": source_id, "source_label": source_label, "client_path_hint": client_path_hint, "skills": skills}
    return self._request("POST", "/tenant/skill-sources/scan", json=payload)
```

```python
scan_parser = skills_subparsers.add_parser("scan")
scan_parser.add_argument("--source-path", required=True)
scan_parser.add_argument("--source-label")
scan_parser.add_argument("--source-id")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-cli\tests\test_client.py .\intent-hub-cli\tests\test_cli.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-cli/intent_hub_cli/skill_collector.py intent-hub-cli/intent_hub_cli/client.py intent-hub-cli/intent_hub_cli/cli.py intent-hub-cli/tests/test_client.py intent-hub-cli/tests/test_cli.py
git commit -m "feat: add client-side skill collection for cli and sdk"
```

## Task 6: Rework Web Tenant Skill Source Page for Local Directory Upload

**Files:**
- Modify: `intent-hub-frontend/src/api/index.ts`
- Modify: `intent-hub-frontend/src/views/tenant/SkillSources.vue`
- Test: frontend manual verification during development

- [ ] **Step 1: Write the failing API and component expectations**

```ts
export interface SkillSourceRecord {
  source_id: string;
  source_label: string;
  enabled: boolean;
  sync_mode: 'scan' | 'apply';
  client_path_hint?: string | null;
}

export interface UploadedSkillItem {
  skill_name: string;
  relative_path: string;
  content: string;
}

export const scanSkillSources = (data: {
  source_id?: string;
  source_label?: string;
  client_path_hint?: string;
  skills: UploadedSkillItem[];
}) => api.post('/tenant/skill-sources/scan', data);
```

```vue
<input ref="directoryInput" type="file" webkitdirectory multiple hidden @change="handleDirectorySelected" />
<el-button type="primary" @click="openDirectoryPicker">选择本地目录</el-button>
<el-table-column prop="source_label" label="Source" />
```

- [ ] **Step 2: Run frontend build to verify it fails**

Run: `npm run build`
Expected: FAIL because the page and API types still assume `path` and do not support local directory upload.

- [ ] **Step 3: Implement minimal page and API changes**

```ts
const pendingSkills = ref<UploadedSkillItem[]>([]);
const pendingFolderName = ref('');

const openDirectoryPicker = () => {
  directoryInput.value?.click();
};

const handleDirectorySelected = async (event: Event) => {
  const input = event.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  const skillFiles = files.filter((file) => file.name === 'SKILL.md');
  pendingSkills.value = await Promise.all(
    skillFiles.map(async (file) => ({
      skill_name: file.webkitRelativePath.split('/').slice(-2, -1)[0] || 'skill',
      relative_path: file.webkitRelativePath,
      content: await file.text(),
    }))
  );
  pendingFolderName.value = skillFiles[0]?.webkitRelativePath.split('/')[0] || '';
};

const uploadSelectedSkills = async () => {
  await scanSkillSources({
    source_id: selectedSourceId.value || undefined,
    source_label: createForm.value.source_label || pendingFolderName.value,
    skills: pendingSkills.value,
  });
};
```

- [ ] **Step 4: Run frontend build to verify it passes**

Run: `npm run build`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add intent-hub-frontend/src/api/index.ts intent-hub-frontend/src/views/tenant/SkillSources.vue
git commit -m "feat: upload local skill directories from web ui"
```

## Task 7: Update User-Facing Documentation

**Files:**
- Modify: `USER_GUIDE.md`
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `intent-hub-cli/README.md`
- Test: `intent-hub-cli/tests/test_docs.py`

- [ ] **Step 1: Write the failing doc expectation**

```python
def test_cli_readme_mentions_source_path_scan():
    readme = Path("intent-hub-cli/README.md").read_text(encoding="utf-8")
    assert "intent-hub skills scan --source-path" in readme
    assert "client-side" in readme.lower() or "local directory" in readme.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest .\intent-hub-cli\tests\test_docs.py -q`
Expected: FAIL because docs still describe backend-side scan behavior.

- [ ] **Step 3: Update docs with the new workflow**

```md
intent-hub skills scan --source-path ./skills --source-label "My Local Skills"
```

```md
- CLI/SDK scan your local directory and upload discovered `SKILL.md` files to the server.
- The Web UI reads a user-selected local directory in the browser and uploads matching `SKILL.md` files.
- The backend no longer scans arbitrary server filesystem paths on behalf of remote users.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest .\intent-hub-cli\tests\test_docs.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add USER_GUIDE.md README.md README.zh-CN.md intent-hub-cli/README.md intent-hub-cli/tests/test_docs.py
git commit -m "docs: document client-side skill scan flow"
```

## Task 8: Full Verification Pass

**Files:**
- Modify: none expected
- Test: backend, CLI, and frontend verification commands

- [ ] **Step 1: Run backend test suite for changed areas**

Run: `pytest .\intent-hub-backend\tests\test_skill_scan_service.py .\intent-hub-backend\tests\test_tenant_skill_api.py .\intent-hub-backend\tests\test_tenant_registry.py -q`
Expected: PASS

- [ ] **Step 2: Run CLI test suite for changed areas**

Run: `pytest .\intent-hub-cli\tests\test_client.py .\intent-hub-cli\tests\test_cli.py .\intent-hub-cli\tests\test_docs.py -q`
Expected: PASS

- [ ] **Step 3: Run frontend production build**

Run: `npm run build`
Expected: PASS

- [ ] **Step 4: Perform manual smoke checks**

```text
1. Start backend and frontend locally.
2. In Web UI, create a logical source label and select a local directory containing at least one <skill_name>/SKILL.md file.
3. Upload and verify the source list shows source_label, discovered count feedback, and no backend path semantics.
4. Re-run upload by selecting the same directory again and verify no duplicate source records are created when source_id is reused.
5. Run `intent-hub skills scan --source-path <dir>` and verify it returns source_id plus discovered/uploaded counts.
```

- [ ] **Step 5: Commit final integration state**

```bash
git add intent-hub-backend intent-hub-cli intent-hub-frontend USER_GUIDE.md README.md README.zh-CN.md
git commit -m "feat: move skill scan to client-side uploads"
```
