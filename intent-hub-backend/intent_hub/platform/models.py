"""Platform and tenant metadata models."""

from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AccessCodeRecord(BaseModel):
    """Stored tenant access code metadata."""

    code_id: str = Field(..., description="Stable access code record ID")
    label: str = Field(..., description="Human-readable label")
    code_hash: str = Field(..., description="SHA-256 hash of the access code")
    status: Literal["active", "disabled"] = Field(
        default="active", description="Whether the code can still be used"
    )
    created_at: str = Field(..., description="RFC3339 timestamp")
    last_used_at: Optional[str] = Field(default=None, description="RFC3339 timestamp")


class SkillSourceRecord(BaseModel):
    """Configured skills source for one tenant."""

    source_id: str = Field(..., description="Stable source ID")
    path: str = Field(..., description="Skills root directory")
    enabled: bool = Field(default=True, description="Whether source is active")
    sync_mode: Literal["scan", "apply"] = Field(
        default="scan", description="Skill source sync mode"
    )
    source_label: Optional[str] = Field(
        default=None,
        description="Human-readable label for this source",
    )
    client_path_hint: Optional[str] = Field(
        default=None,
        description="Hint for client-local directory selection",
    )


class TenantRecord(BaseModel):
    """Tenant metadata stored in platform registry."""

    tenant_id: str = Field(..., description="Stable tenant identifier")
    name: str = Field(..., description="Tenant display name")
    status: Literal["active", "disabled"] = Field(
        default="active", description="Whether the tenant is active"
    )
    qdrant_collection: str = Field(..., description="Tenant collection name")
    access_codes: list[AccessCodeRecord] = Field(default_factory=list)
    skill_sources: list[SkillSourceRecord] = Field(default_factory=list)


class TenantWorkspacePaths(BaseModel):
    """Resolved tenant workspace paths."""

    tenant_id: str
    workspace_dir: Path
    settings_path: Path
    routes_path: Path
    diagnostics_cache_path: Path
    skills_index_path: Path
    imports_dir: Path

    model_config = {"arbitrary_types_allowed": True}
