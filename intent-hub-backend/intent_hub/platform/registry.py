"""Platform tenant registry."""

import hashlib
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from intent_hub.platform.models import AccessCodeRecord, TenantRecord
from intent_hub.platform.models import SkillSourceRecord


class TenantRegistry:
    """Load and query tenant metadata."""

    def __init__(self, tenants_file: Path | str):
        self.tenants_file = Path(tenants_file)
        self._tenants = self._load_tenants()

    def reload(self) -> list[TenantRecord]:
        self._tenants = self._load_tenants()
        return self._tenants

    @staticmethod
    def hash_access_code(access_code: str) -> str:
        normalized = (access_code or "").strip()
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return f"sha256:{digest}"

    def _load_tenants(self) -> list[TenantRecord]:
        if not self.tenants_file.exists():
            return []

        raw = json.loads(self.tenants_file.read_text(encoding="utf-8"))
        return [TenantRecord.model_validate(item) for item in raw]

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _default_collection_name(tenant_id: str) -> str:
        return f"intent_hub_{tenant_id}"

    @staticmethod
    def _generate_access_code(tenant_id: str) -> str:
        return f"ih_live_{tenant_id}_{secrets.token_hex(12)}"

    def _next_code_id(self, tenant: TenantRecord) -> str:
        next_index = len(tenant.access_codes) + 1
        return f"ac_{next_index:03d}"

    def _next_source_id(self, tenant: TenantRecord) -> str:
        next_index = len(tenant.skill_sources) + 1
        return f"src_{next_index:03d}"

    def _save_tenants(self) -> None:
        self.tenants_file.parent.mkdir(parents=True, exist_ok=True)
        payload = [tenant.model_dump(mode="json") for tenant in self._tenants]
        self.tenants_file.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_tenants(self) -> list[TenantRecord]:
        self.reload()
        return list(self._tenants)

    def get_tenant(self, tenant_id: str) -> Optional[TenantRecord]:
        self.reload()
        for tenant in self._tenants:
            if tenant.tenant_id == tenant_id:
                return tenant
        return None

    def get_tenant_by_access_code(self, access_code: str) -> Optional[TenantRecord]:
        self.reload()
        code_hash = self.hash_access_code(access_code)

        for tenant in self._tenants:
            if tenant.status != "active":
                continue

            for code in tenant.access_codes:
                if code.status != "active":
                    continue
                if code.code_hash == code_hash:
                    return tenant

        return None

    def create_tenant(
        self,
        tenant_id: str,
        name: str,
        qdrant_collection: Optional[str] = None,
        access_code_label: str = "default",
        access_code: Optional[str] = None,
    ) -> tuple[TenantRecord, AccessCodeRecord, str]:
        self.reload()
        tenant_id = (tenant_id or "").strip()
        name = (name or "").strip()
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not name:
            raise ValueError("name is required")
        if self.get_tenant(tenant_id) is not None:
            raise ValueError(f"Tenant already exists: {tenant_id}")

        plain_code = (access_code or self._generate_access_code(tenant_id)).strip()
        created_at = self._utc_now()
        code_record = AccessCodeRecord(
            code_id="ac_001",
            label=(access_code_label or "default").strip() or "default",
            code_hash=self.hash_access_code(plain_code),
            status="active",
            created_at=created_at,
            last_used_at=None,
        )
        tenant = TenantRecord(
            tenant_id=tenant_id,
            name=name,
            status="active",
            qdrant_collection=(qdrant_collection or self._default_collection_name(tenant_id)).strip(),
            access_codes=[code_record],
            skill_sources=[],
        )
        self._tenants.append(tenant)
        self._save_tenants()
        return tenant, code_record, plain_code

    def create_access_code(
        self,
        tenant_id: str,
        label: str,
        access_code: Optional[str] = None,
    ) -> tuple[TenantRecord, AccessCodeRecord, str]:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")

        plain_code = (access_code or self._generate_access_code(tenant_id)).strip()
        code_record = AccessCodeRecord(
            code_id=self._next_code_id(tenant),
            label=(label or "").strip() or "default",
            code_hash=self.hash_access_code(plain_code),
            status="active",
            created_at=self._utc_now(),
            last_used_at=None,
        )
        tenant.access_codes.append(code_record)
        self._save_tenants()
        return tenant, code_record, plain_code

    def rotate_access_code(
        self,
        tenant_id: str,
        code_id: str,
        access_code: Optional[str] = None,
    ) -> tuple[TenantRecord, AccessCodeRecord, str]:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")

        target = next((code for code in tenant.access_codes if code.code_id == code_id), None)
        if target is None:
            raise ValueError(f"Access code not found: {code_id}")
        if target.status != "active":
            raise ValueError(f"Access code is not active: {code_id}")

        plain_code = (access_code or self._generate_access_code(tenant_id)).strip()
        target.code_hash = self.hash_access_code(plain_code)
        target.created_at = self._utc_now()
        target.last_used_at = None
        self._save_tenants()
        return tenant, target, plain_code

    def disable_access_code(self, tenant_id: str, code_id: str) -> tuple[TenantRecord, AccessCodeRecord]:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")

        target = next((code for code in tenant.access_codes if code.code_id == code_id), None)
        if target is None:
            raise ValueError(f"Access code not found: {code_id}")

        target.status = "disabled"
        self._save_tenants()
        return tenant, target

    def list_skill_sources(self, tenant_id: str) -> list[SkillSourceRecord]:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")
        return list(tenant.skill_sources)

    def create_skill_source(
        self,
        tenant_id: str,
        path: str,
        source_label: str | None = None,
        sync_mode: str = "apply",
        enabled: bool = True,
    ) -> tuple[TenantRecord, SkillSourceRecord]:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")
        normalized_path = (path or "").strip()
        if not normalized_path:
            raise ValueError("path is required")
        label = (source_label or "").strip()
        if not label:
            label = Path(normalized_path).name or self._next_source_id(tenant)
        source = SkillSourceRecord(
            source_id=self._next_source_id(tenant),
            path=normalized_path,
            enabled=enabled,
            sync_mode=sync_mode,
            source_label=label,
            client_path_hint=normalized_path,
        )
        tenant.skill_sources.append(source)
        self._save_tenants()
        return tenant, source

    def update_skill_source(
        self,
        tenant_id: str,
        source: SkillSourceRecord,
    ) -> TenantRecord:
        self.reload()
        tenant = self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")
        for index, existing in enumerate(tenant.skill_sources):
            if existing.source_id == source.source_id:
                tenant.skill_sources[index] = source
                self._save_tenants()
                return tenant
        tenant.skill_sources.append(source)
        self._save_tenants()
        return tenant
