"""Tenant workspace path resolution."""

from pathlib import Path

from intent_hub.platform.models import TenantRecord, TenantWorkspacePaths


class TenantWorkspaceResolver:
    """Resolve workspace paths for a tenant."""

    def __init__(self, data_dir: Path | str, tenant: TenantRecord):
        self.data_dir = Path(data_dir)
        self.tenant = tenant

    def resolve(self) -> TenantWorkspacePaths:
        tenant_workspace_dir = self.data_dir / "tenants" / self.tenant.tenant_id

        if self.tenant.tenant_id == "default":
            routes_path = self._legacy_or_default("routes.json")
            settings_path = self._legacy_or_default("settings.json")
            diagnostics_cache_path = self._legacy_or_default("diagnostics_cache.json")
        else:
            routes_path = tenant_workspace_dir / "routes.json"
            settings_path = tenant_workspace_dir / "settings.json"
            diagnostics_cache_path = tenant_workspace_dir / "diagnostics_cache.json"

        return TenantWorkspacePaths(
            tenant_id=self.tenant.tenant_id,
            workspace_dir=tenant_workspace_dir,
            settings_path=settings_path,
            routes_path=routes_path,
            diagnostics_cache_path=diagnostics_cache_path,
            skills_index_path=tenant_workspace_dir / "skills_index.json",
            imports_dir=tenant_workspace_dir / "imports",
        )

    def _legacy_or_default(self, filename: str) -> Path:
        legacy_path = self.data_dir / filename
        if legacy_path.exists():
            return legacy_path
        return self.data_dir / "tenants" / self.tenant.tenant_id / filename
