"""Platform admin APIs."""

from flask import jsonify, request

from intent_hub.auth import require_auth
from intent_hub.config import Config
from intent_hub.platform.registry import TenantRegistry
from intent_hub.utils.error_handler import handle_errors


_tenant_registry: TenantRegistry | None = None


def get_tenant_registry() -> TenantRegistry:
    global _tenant_registry
    if _tenant_registry is None:
        _tenant_registry = TenantRegistry(Config.PLATFORM_DATA_DIR / "tenants.json")
    return _tenant_registry


def _serialize_access_code(code, access_code: str | None = None) -> dict:
    payload = {
        "code_id": code.code_id,
        "label": code.label,
        "status": code.status,
        "created_at": code.created_at,
        "last_used_at": code.last_used_at,
    }
    if access_code is not None:
        payload["access_code"] = access_code
    return payload


def _serialize_tenant(tenant) -> dict:
    return {
        "tenant_id": tenant.tenant_id,
        "name": tenant.name,
        "status": tenant.status,
        "qdrant_collection": tenant.qdrant_collection,
        "access_codes": [_serialize_access_code(code) for code in tenant.access_codes],
        "skill_sources": [source.model_dump(mode="json") for source in tenant.skill_sources],
    }


@handle_errors
@require_auth
def list_tenants():
    registry = get_tenant_registry()
    return jsonify({"items": [_serialize_tenant(tenant) for tenant in registry.list_tenants()]}), 200


@handle_errors
@require_auth
def create_tenant():
    data = request.get_json() or {}
    registry = get_tenant_registry()
    tenant, code_record, plain_code = registry.create_tenant(
        tenant_id=data.get("tenant_id", ""),
        name=data.get("name", ""),
        qdrant_collection=data.get("qdrant_collection"),
        access_code_label=data.get("access_code_label", "default"),
        access_code=data.get("access_code"),
    )
    return jsonify(
        {
            "tenant": _serialize_tenant(tenant),
            "access_code": _serialize_access_code(code_record, access_code=plain_code),
        }
    ), 201


@handle_errors
@require_auth
def create_access_code(tenant_id: str):
    data = request.get_json() or {}
    registry = get_tenant_registry()
    tenant, code_record, plain_code = registry.create_access_code(
        tenant_id=tenant_id,
        label=data.get("label", ""),
        access_code=data.get("access_code"),
    )
    return jsonify(
        {
            "tenant": _serialize_tenant(tenant),
            "access_code": _serialize_access_code(code_record, access_code=plain_code),
        }
    ), 201


@handle_errors
@require_auth
def rotate_access_code(tenant_id: str, code_id: str):
    registry = get_tenant_registry()
    tenant, code_record, plain_code = registry.rotate_access_code(tenant_id=tenant_id, code_id=code_id)
    return jsonify(
        {
            "tenant": _serialize_tenant(tenant),
            "access_code": _serialize_access_code(code_record, access_code=plain_code),
        }
    ), 200


@handle_errors
@require_auth
def disable_access_code(tenant_id: str, code_id: str):
    registry = get_tenant_registry()
    tenant, code_record = registry.disable_access_code(tenant_id=tenant_id, code_id=code_id)
    return jsonify(
        {
            "tenant": _serialize_tenant(tenant),
            "access_code": _serialize_access_code(code_record),
        }
    ), 200
