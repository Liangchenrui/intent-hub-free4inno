import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.platform.models import AccessCodeRecord, SkillSourceRecord, TenantRecord
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


def test_tenant_registry_finds_tenant_by_access_code_hash(test_dir):
    platform_dir = test_dir / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)

    access_code = "ih_live_team_alpha"
    code_hash = TenantRegistry.hash_access_code(access_code)
    tenants_file = platform_dir / "tenants.json"
    tenants_file.write_text(
        json.dumps(
            [
                {
                    "tenant_id": "team_alpha",
                    "name": "Team Alpha",
                    "status": "active",
                    "qdrant_collection": "intent_hub_team_alpha",
                    "access_codes": [
                        {
                            "code_id": "ac_001",
                            "label": "default",
                            "code_hash": code_hash,
                            "status": "active",
                            "created_at": "2026-04-14T10:00:00Z",
                            "last_used_at": None,
                        }
                    ],
                    "skill_sources": [],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = TenantRegistry(tenants_file)
    tenant = registry.get_tenant_by_access_code(access_code)

    assert tenant is not None
    assert tenant.tenant_id == "team_alpha"
    assert tenant.qdrant_collection == "intent_hub_team_alpha"


def test_tenant_registry_rejects_disabled_access_code(test_dir):
    platform_dir = test_dir / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)

    access_code = "ih_live_disabled"
    tenants_file = platform_dir / "tenants.json"
    tenants_file.write_text(
        json.dumps(
            [
                {
                    "tenant_id": "team_alpha",
                    "name": "Team Alpha",
                    "status": "active",
                    "qdrant_collection": "intent_hub_team_alpha",
                    "access_codes": [
                        {
                            "code_id": "ac_001",
                            "label": "default",
                            "code_hash": TenantRegistry.hash_access_code(access_code),
                            "status": "disabled",
                            "created_at": "2026-04-14T10:00:00Z",
                            "last_used_at": None,
                        }
                    ],
                    "skill_sources": [],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = TenantRegistry(tenants_file)

    assert registry.get_tenant_by_access_code(access_code) is None


def test_workspace_resolver_uses_legacy_files_for_default_tenant(test_dir):
    legacy_routes = test_dir / "routes.json"
    legacy_settings = test_dir / "settings.json"
    legacy_diagnostics = test_dir / "diagnostics_cache.json"
    legacy_routes.write_text("[]", encoding="utf-8")
    legacy_settings.write_text("{}", encoding="utf-8")
    legacy_diagnostics.write_text("{}", encoding="utf-8")

    resolver = TenantWorkspaceResolver(
        data_dir=test_dir,
        tenant=TenantRecord(
            tenant_id="default",
            name="Default Tenant",
            status="active",
            qdrant_collection="intent_hub_routes",
            access_codes=[
                AccessCodeRecord(
                    code_id="ac_default",
                    label="default",
                    code_hash="sha256:abc",
                    status="active",
                    created_at="2026-04-14T10:00:00Z",
                    last_used_at=None,
                )
            ],
            skill_sources=[
                SkillSourceRecord(
                    source_id="src_001",
                    path="D:/skills/default",
                    enabled=True,
                    sync_mode="scan",
                )
            ],
        ),
    )

    workspace = resolver.resolve()

    assert workspace.tenant_id == "default"
    assert workspace.routes_path == legacy_routes
    assert workspace.settings_path == legacy_settings
    assert workspace.diagnostics_cache_path == legacy_diagnostics
    assert workspace.skills_index_path == test_dir / "tenants" / "default" / "skills_index.json"
    assert workspace.imports_dir == test_dir / "tenants" / "default" / "imports"


def test_tenant_context_can_be_built_from_tenant_and_workspace(test_dir):
    tenant = TenantRecord(
        tenant_id="team_alpha",
        name="Team Alpha",
        status="active",
        qdrant_collection="intent_hub_team_alpha",
        access_codes=[],
        skill_sources=[],
    )
    resolver = TenantWorkspaceResolver(data_dir=test_dir, tenant=tenant)

    context = TenantContext.from_tenant_record(tenant, resolver.resolve())

    assert context.tenant_id == "team_alpha"
    assert context.tenant_name == "Team Alpha"
    assert context.collection_name == "intent_hub_team_alpha"
    assert context.workspace_dir == test_dir / "tenants" / "team_alpha"
    assert context.routes_path == test_dir / "tenants" / "team_alpha" / "routes.json"


def test_skill_source_record_has_source_label_and_client_path_hint():
    source = SkillSourceRecord(
        source_id="src_001",
        path="/some/path",
        enabled=True,
        sync_mode="scan",
        source_label="My Skill Source",
        client_path_hint="/client/side/path",
    )

    assert source.source_label == "My Skill Source"
    assert source.client_path_hint == "/client/side/path"


def test_create_skill_source_sets_source_label_from_basename(test_dir):
    platform_dir = test_dir / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)
    tenants_file = platform_dir / "tenants.json"
    tenants_file.write_text("[]", encoding="utf-8")

    registry = TenantRegistry(tenants_file)

    registry.create_tenant(tenant_id="test_tenant", name="Test Tenant")

    updated_tenant, source = registry.create_skill_source(
        tenant_id="test_tenant",
        path="/some/path/to/my_skills",
        sync_mode="scan",
        enabled=True,
    )

    assert updated_tenant.skill_sources[0].source_id == source.source_id
    assert source.source_label == "my_skills"
    assert source.client_path_hint == "/some/path/to/my_skills"


def test_create_skill_source_with_explicit_source_label(test_dir):
    platform_dir = test_dir / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)
    tenants_file = platform_dir / "tenants.json"
    tenants_file.write_text("[]", encoding="utf-8")

    registry = TenantRegistry(tenants_file)

    registry.create_tenant(tenant_id="test_tenant", name="Test Tenant")

    _, source = registry.create_skill_source(
        tenant_id="test_tenant",
        path="/some/path/to/my_skills",
        source_label="My Local Skills",
        sync_mode="apply",
        enabled=True,
    )

    assert source.source_label == "My Local Skills"
    assert source.client_path_hint == "/some/path/to/my_skills"


def test_backward_compatibility_with_existing_json(test_dir):
    platform_dir = test_dir / "platform"
    platform_dir.mkdir(parents=True, exist_ok=True)

    tenants_file = platform_dir / "tenants.json"
    tenants_file.write_text(
        json.dumps(
            [
                {
                    "tenant_id": "old_tenant",
                    "name": "Old Tenant",
                    "status": "active",
                    "qdrant_collection": "intent_hub_old",
                    "access_codes": [],
                    "skill_sources": [
                        {
                            "source_id": "src_001",
                            "path": "/old/path",
                            "enabled": True,
                            "sync_mode": "scan",
                        }
                    ],
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    registry = TenantRegistry(tenants_file)
    tenant = registry.get_tenant("old_tenant")

    assert tenant is not None
    assert len(tenant.skill_sources) == 1
    source = tenant.skill_sources[0]

    assert source.path == "/old/path"
    assert source.source_label is None
    assert source.client_path_hint is None
