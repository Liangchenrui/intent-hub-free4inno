import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.app import app
from intent_hub.platform.models import SkillSourceRecord, TenantRecord
from intent_hub.platform.registry import TenantRegistry
from intent_hub.platform.workspace import TenantWorkspaceResolver
from intent_hub.tenant.context import TenantContext


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_tenant(test_dir: Path) -> tuple[TenantRegistry, TenantContext]:
    tenants_file = test_dir / "platform" / "tenants.json"
    tenants_file.parent.mkdir(parents=True, exist_ok=True)
    registry = TenantRegistry(tenants_file)
    tenant, code_record, _ = registry.create_tenant(
        tenant_id="team_alpha",
        name="Team Alpha",
        access_code="ih_live_team_alpha",
    )
    workspace = TenantWorkspaceResolver(test_dir, tenant).resolve()
    context = TenantContext.from_tenant_record(tenant, workspace)
    return registry, context


class DummyTenantAuthService:
    def __init__(self, tenant_context: TenantContext, tenant_record):
        self.tenant_context = tenant_context
        self.tenant_record = tenant_record

    def authenticate_access_code(self, access_code: str):
        if access_code != "ih_live_team_alpha":
            raise ValueError("Invalid or disabled access code")
        code = type("AccessCode", (), {"code_id": "ac_001", "label": "default"})()
        return self.tenant_context, self.tenant_record, code


class DummyTenantComponentRegistry:
    def __init__(self, tenant_context: TenantContext):
        self.tenant_context = tenant_context

    def get(self, tenant_context):
        return type(
            "Manager",
            (),
            {
                "context": tenant_context,
                "route_manager": None,
                "ensure_ready": lambda self: None,
            },
        )()


def test_tenant_skill_source_create_and_list(test_dir, monkeypatch):
    registry, context = make_tenant(test_dir)
    tenant_record = registry.get_tenant("team_alpha")

    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService(context, tenant_record))
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_registry", lambda: registry)

    client = app.test_client()

    create_response = client.post(
        "/tenant/skill-sources",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"path": str(test_dir / "skills"), "sync_mode": "draft"},
    )
    assert create_response.status_code == 201
    created = create_response.get_json()
    assert created["item"]["source_id"] == "src_001"

    list_response = client.get(
        "/tenant/skill-sources",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
    )
    assert list_response.status_code == 200
    payload = list_response.get_json()
    assert payload["items"][0]["path"] == str(test_dir / "skills")


def test_tenant_skill_scan_and_list_drafts(test_dir, monkeypatch):
    registry, context = make_tenant(test_dir)
    skills_root = test_dir / "skills"
    (skills_root / "wiki_builder").mkdir(parents=True, exist_ok=True)
    (skills_root / "wiki_builder" / "SKILL.md").write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")
    tenant_record = registry.update_skill_source(
        "team_alpha",
        SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft"),
    )

    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService(context, tenant_record))
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_registry", lambda: registry)
    monkeypatch.setattr(
        "intent_hub.api.tenant.build_skill_draft_generator",
        lambda component_manager: (
            lambda skill_file, content: {
                "mode": "merge",
                "routes": [
                    {
                        "id": 0,
                        "name": skill_file.parent.name,
                        "route_key": "wiki.builder",
                        "description": content.splitlines()[0],
                        "utterances": ["整理 wiki"],
                        "negative_samples": [],
                        "score_threshold": 0.75,
                        "negative_threshold": 0.95,
                        "source": {
                            "type": "json_import",
                            "import_origin": "skill_scan",
                            "managed_fields": [],
                        },
                        "sync": {"status": "pending", "last_synced_at": None, "manual_overrides": []},
                        "lifecycle_status": "active",
                    }
                ],
            }
        ),
    )
    monkeypatch.setattr(
        "intent_hub.api.tenant.get_tenant_component_registry",
        lambda: DummyTenantComponentRegistry(context),
    )

    client = app.test_client()

    scan_response = client.post(
        "/tenant/skill-sources/scan",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
    )
    assert scan_response.status_code == 200
    assert scan_response.get_json()["discovered"] == 1

    drafts_response = client.get(
        "/tenant/skill-drafts",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
    )
    assert drafts_response.status_code == 200
    payload = drafts_response.get_json()
    assert payload["items"][0]["status"] == "draft"
    assert payload["items"][0]["draft_file"].endswith(".json")


def test_tenant_skill_draft_apply_imports_routes(test_dir, monkeypatch):
    registry, context = make_tenant(test_dir)
    context.routes_path.parent.mkdir(parents=True, exist_ok=True)
    context.routes_path.write_text("[]", encoding="utf-8")
    context.imports_dir.mkdir(parents=True, exist_ok=True)
    draft_path = context.imports_dir / "skills" / "src_001" / "wiki_builder.json"
    draft_path.parent.mkdir(parents=True, exist_ok=True)
    draft_path.write_text(
        json.dumps(
            {
                "mode": "merge",
                "routes": [
                    {
                        "id": 0,
                        "name": "Wiki Builder",
                        "route_key": "wiki.builder",
                        "description": "build wiki",
                        "utterances": ["整理 wiki"],
                        "negative_samples": [],
                        "score_threshold": 0.75,
                        "negative_threshold": 0.95,
                        "source": {"type": "json_import", "import_origin": "skill_scan", "managed_fields": []},
                        "sync": {"status": "pending", "last_synced_at": None, "manual_overrides": []},
                        "lifecycle_status": "active",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    context.skills_index_path.parent.mkdir(parents=True, exist_ok=True)
    context.skills_index_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "source_id": "src_001",
                        "skill_path": str(test_dir / "skills" / "wiki_builder" / "SKILL.md"),
                        "draft_file": str(draft_path),
                        "status": "draft",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    tenant_record = registry.get_tenant("team_alpha")

    monkeypatch.setattr("intent_hub.auth.get_tenant_auth_service", lambda: DummyTenantAuthService(context, tenant_record))
    monkeypatch.setattr("intent_hub.api.tenant.get_tenant_registry", lambda: registry)
    monkeypatch.setattr(
        "intent_hub.api.tenant.get_tenant_component_registry",
        lambda: DummyTenantComponentRegistry(context),
    )

    from intent_hub.route_manager import RouteManager

    class DummyManager:
        def __init__(self, tenant_context):
            self.context = tenant_context
            self.route_manager = RouteManager(config_path=str(tenant_context.routes_path))

        def ensure_ready(self):
            return None

    monkeypatch.setattr(
        "intent_hub.api.tenant.get_tenant_component_registry",
        lambda: type("Registry", (), {"get": lambda self, tenant_context: DummyManager(tenant_context)})(),
    )

    client = app.test_client()
    apply_response = client.post(
        "/tenant/skill-drafts/apply",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"draft_file": str(draft_path)},
    )

    assert apply_response.status_code == 200
    payload = apply_response.get_json()
    assert payload["created"] == 1
    routes = json.loads(context.routes_path.read_text(encoding="utf-8"))
    assert routes[0]["route_key"] == "wiki.builder"
