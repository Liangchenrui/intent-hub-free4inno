"""One-time migration from legacy single-tenant files to default tenant workspace."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from intent_hub.config import Config
from intent_hub.platform.registry import TenantRegistry


def _backup_file(path: Path) -> None:
    if not path.exists():
        return
    backup_path = path.with_suffix(path.suffix + ".bak")
    if backup_path.exists():
        return
    shutil.copy2(path, backup_path)


def _copy_if_exists(src: Path, dst: Path) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def migrate() -> None:
    data_dir = Config.DATA_DIR
    platform_dir = Config.PLATFORM_DATA_DIR
    tenant_dir = Config.TENANTS_DATA_DIR / Config.DEFAULT_TENANT_ID

    legacy_routes = data_dir / "routes.json"
    legacy_settings = data_dir / "settings.json"
    legacy_diagnostics = data_dir / "diagnostics_cache.json"

    for legacy_file in (legacy_routes, legacy_settings, legacy_diagnostics):
        _backup_file(legacy_file)

    _copy_if_exists(legacy_routes, tenant_dir / "routes.json")
    _copy_if_exists(legacy_settings, tenant_dir / "settings.json")
    _copy_if_exists(legacy_diagnostics, tenant_dir / "diagnostics_cache.json")

    (tenant_dir / "imports").mkdir(parents=True, exist_ok=True)
    skills_index_path = tenant_dir / "skills_index.json"
    if not skills_index_path.exists():
        skills_index_path.write_text(json.dumps({"items": []}, ensure_ascii=False, indent=2), encoding="utf-8")

    tenants_file = platform_dir / "tenants.json"
    registry = TenantRegistry(tenants_file)
    if registry.get_tenant(Config.DEFAULT_TENANT_ID) is None:
        registry.create_tenant(
            tenant_id=Config.DEFAULT_TENANT_ID,
            name="Default Tenant",
            qdrant_collection=Config.QDRANT_COLLECTION or "intent_hub_default",
            access_code="ih_live_default_local",
            access_code_label="default",
        )


if __name__ == "__main__":
    migrate()
    print("Migration completed.")
