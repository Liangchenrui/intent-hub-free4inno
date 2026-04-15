import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.services.tenant_auth_service import TenantAuthService


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def write_tenants_file(test_dir: Path, access_code: str, status: str = "active") -> Path:
    tenants_file = test_dir / "tenants.json"
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
                            "code_hash": TenantAuthService.hash_access_code(access_code),
                            "status": status,
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
    return tenants_file


def test_tenant_auth_service_resolves_context_from_access_code(test_dir):
    tenants_file = write_tenants_file(test_dir, "ih_live_team_alpha")
    service = TenantAuthService(tenants_file=tenants_file, data_dir=test_dir.parent)

    context, tenant, code = service.authenticate_access_code("ih_live_team_alpha")

    assert context.tenant_id == "team_alpha"
    assert tenant.name == "Team Alpha"
    assert code.code_id == "ac_001"


def test_tenant_auth_service_rejects_disabled_code(test_dir):
    tenants_file = write_tenants_file(test_dir, "ih_live_disabled", status="disabled")
    service = TenantAuthService(tenants_file=tenants_file, data_dir=test_dir.parent)

    with pytest.raises(ValueError, match="Invalid or disabled access code"):
        service.authenticate_access_code("ih_live_disabled")
