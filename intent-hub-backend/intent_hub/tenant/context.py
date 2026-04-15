"""Tenant runtime context."""

from pathlib import Path

from pydantic import BaseModel

from intent_hub.platform.models import TenantRecord, TenantWorkspacePaths


class TenantContext(BaseModel):
    """Resolved runtime context for one tenant."""

    tenant_id: str
    tenant_name: str
    collection_name: str
    workspace_dir: Path
    settings_path: Path
    routes_path: Path
    diagnostics_cache_path: Path
    skills_index_path: Path
    imports_dir: Path

    model_config = {"arbitrary_types_allowed": True}

    @classmethod
    def from_tenant_record(
        cls, tenant: TenantRecord, workspace: TenantWorkspacePaths
    ) -> "TenantContext":
        return cls(
            tenant_id=tenant.tenant_id,
            tenant_name=tenant.name,
            collection_name=tenant.qdrant_collection,
            workspace_dir=workspace.workspace_dir,
            settings_path=workspace.settings_path,
            routes_path=workspace.routes_path,
            diagnostics_cache_path=workspace.diagnostics_cache_path,
            skills_index_path=workspace.skills_index_path,
            imports_dir=workspace.imports_dir,
        )
