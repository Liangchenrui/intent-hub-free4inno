import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.app import app
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


def make_context(test_dir: Path) -> tuple[TenantRegistry, TenantContext]:
    tenants_file = test_dir / "platform" / "tenants.json"
    tenants_file.parent.mkdir(parents=True, exist_ok=True)
    registry = TenantRegistry(tenants_file)
    tenant, _, _ = registry.create_tenant(
        tenant_id="team_alpha",
        name="Team Alpha",
        access_code="ih_live_team_alpha",
    )
    workspace = TenantWorkspaceResolver(test_dir, tenant).resolve()
    return registry, TenantContext.from_tenant_record(tenant, workspace)


class DummyTenantAuthService:
    def __init__(self, context, tenant):
        self.context = context
        self.tenant = tenant

    def authenticate_access_code(self, access_code: str):
        if access_code != "ih_live_team_alpha":
            raise ValueError("Invalid or disabled access code")
        code = type("AccessCode", (), {"code_id": "ac_001", "label": "default"})()
        return self.context, self.tenant, code


def test_tenant_settings_read_and_write_tenant_file(test_dir, monkeypatch):
    registry, context = make_context(test_dir)
    tenant = registry.get_tenant("team_alpha")
    context.settings_path.parent.mkdir(parents=True, exist_ok=True)
    context.settings_path.write_text(
        json.dumps({"EMBEDDING_SERVICE_URL": "http://tenant-embed"}, ensure_ascii=False),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "intent_hub.auth.get_tenant_auth_service",
        lambda: DummyTenantAuthService(context, tenant),
    )

    client = app.test_client()
    get_resp = client.get(
        "/tenant/settings",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
    )
    assert get_resp.status_code == 200
    assert get_resp.get_json()["EMBEDDING_SERVICE_URL"] == "http://tenant-embed"

    update_resp = client.post(
        "/tenant/settings",
        headers={"Authorization": "Bearer ih_live_team_alpha"},
        json={"LLM_PROVIDER": "openrouter"},
    )
    assert update_resp.status_code == 200
    stored = json.loads(context.settings_path.read_text(encoding="utf-8"))
    assert stored["LLM_PROVIDER"] == "openrouter"

