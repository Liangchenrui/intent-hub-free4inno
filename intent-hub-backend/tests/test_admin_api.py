import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.app import app
from intent_hub.platform.registry import TenantRegistry


class DummyAuthManager:
    def is_valid(self, key: str) -> bool:
        return key == "admin-key"


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


@pytest.fixture
def admin_registry(test_dir, monkeypatch):
    tenants_file = test_dir / "platform" / "tenants.json"
    tenants_file.parent.mkdir(parents=True, exist_ok=True)
    tenants_file.write_text("[]", encoding="utf-8")

    registry = TenantRegistry(tenants_file)
    monkeypatch.setattr("intent_hub.auth.get_auth_manager", lambda: DummyAuthManager())
    monkeypatch.setattr("intent_hub.api.admin.get_tenant_registry", lambda: registry)
    return registry


def test_admin_can_list_tenants(admin_registry):
    admin_registry.create_tenant(
        tenant_id="team_alpha",
        name="Team Alpha",
        qdrant_collection="intent_hub_team_alpha",
        access_code="ih_live_team_alpha",
    )

    client = app.test_client()
    response = client.get("/admin/tenants", headers={"Authorization": "Bearer admin-key"})

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["items"][0]["tenant_id"] == "team_alpha"
    assert payload["items"][0]["access_codes"][0]["code_id"] == "ac_001"
    assert "code_hash" not in payload["items"][0]["access_codes"][0]


def test_admin_can_create_tenant_with_initial_access_code(admin_registry):
    client = app.test_client()
    response = client.post(
        "/admin/tenants",
        headers={"Authorization": "Bearer admin-key"},
        json={"tenant_id": "team_beta", "name": "Team Beta"},
    )

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["tenant"]["tenant_id"] == "team_beta"
    assert payload["tenant"]["qdrant_collection"] == "intent_hub_team_beta"
    assert payload["access_code"]["label"] == "default"
    assert payload["access_code"]["access_code"].startswith("ih_live_team_beta_")


def test_admin_can_create_rotate_and_disable_access_code(admin_registry):
    admin_registry.create_tenant(
        tenant_id="team_alpha",
        name="Team Alpha",
        qdrant_collection="intent_hub_team_alpha",
        access_code="ih_live_team_alpha",
    )

    client = app.test_client()

    create_response = client.post(
        "/admin/tenants/team_alpha/access-codes",
        headers={"Authorization": "Bearer admin-key"},
        json={"label": "cli"},
    )
    assert create_response.status_code == 201
    created_payload = create_response.get_json()
    code_id = created_payload["access_code"]["code_id"]
    assert created_payload["access_code"]["label"] == "cli"
    assert created_payload["access_code"]["access_code"].startswith("ih_live_team_alpha_")

    rotate_response = client.post(
        f"/admin/tenants/team_alpha/access-codes/{code_id}/rotate",
        headers={"Authorization": "Bearer admin-key"},
    )
    assert rotate_response.status_code == 200
    rotated_payload = rotate_response.get_json()
    assert rotated_payload["access_code"]["code_id"] == code_id
    assert rotated_payload["access_code"]["access_code"].startswith("ih_live_team_alpha_")

    disable_response = client.post(
        f"/admin/tenants/team_alpha/access-codes/{code_id}/disable",
        headers={"Authorization": "Bearer admin-key"},
    )
    assert disable_response.status_code == 200
    disabled_payload = disable_response.get_json()
    assert disabled_payload["access_code"]["code_id"] == code_id
    assert disabled_payload["access_code"]["status"] == "disabled"

    stored = json.loads(admin_registry.tenants_file.read_text(encoding="utf-8"))
    codes = stored[0]["access_codes"]
    disabled_record = next(item for item in codes if item["code_id"] == code_id)
    assert disabled_record["status"] == "disabled"
