"""Tenant access code authentication service."""

from pathlib import Path

from intent_hub.config import Config
from intent_hub.platform.registry import TenantRegistry
from intent_hub.platform.workspace import TenantWorkspaceResolver
from intent_hub.tenant.context import TenantContext


class TenantAuthService:
    """Resolve tenant context from access code."""

    def __init__(self, tenants_file: Path | str | None = None, data_dir: Path | str | None = None):
        self.data_dir = Path(data_dir) if data_dir is not None else Config.DATA_DIR
        self.tenants_file = (
            Path(tenants_file)
            if tenants_file is not None
            else Config.PLATFORM_DATA_DIR / "tenants.json"
        )
        self.registry = TenantRegistry(self.tenants_file)

    @staticmethod
    def hash_access_code(access_code: str) -> str:
        return TenantRegistry.hash_access_code(access_code)

    def authenticate_access_code(self, access_code: str):
        tenant = self.registry.get_tenant_by_access_code(access_code)
        if tenant is None:
            raise ValueError("Invalid or disabled access code")

        workspace = TenantWorkspaceResolver(self.data_dir, tenant).resolve()
        context = TenantContext.from_tenant_record(tenant, workspace)

        matched_code = next(
            (
                code
                for code in tenant.access_codes
                if code.status == "active" and code.code_hash == self.hash_access_code(access_code)
            ),
            None,
        )
        if matched_code is None:
            raise ValueError("Invalid or disabled access code")

        return context, tenant, matched_code
