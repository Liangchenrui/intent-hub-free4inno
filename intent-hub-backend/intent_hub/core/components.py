"""Backward-compatible component access built on tenant-scoped managers."""

from typing import Optional

from intent_hub.config import Config
from intent_hub.platform.models import TenantRecord
from intent_hub.platform.workspace import TenantWorkspaceResolver
from intent_hub.tenant.components import TenantComponentRegistry
from intent_hub.tenant.context import TenantContext


class ComponentManager:
    """Compatibility wrapper that exposes the default tenant components."""

    def __init__(
        self,
        encoder_factory=None,
        qdrant_client_factory=None,
        route_manager_factory=None,
    ):
        self._registry = TenantComponentRegistry(
            encoder_factory=encoder_factory,
            qdrant_client_factory=qdrant_client_factory,
            route_manager_factory=route_manager_factory,
        )

    @property
    def tenant_context(self) -> TenantContext:
        tenant = TenantRecord(
            tenant_id=Config.DEFAULT_TENANT_ID,
            name="Default Tenant",
            status="active",
            qdrant_collection=Config.QDRANT_COLLECTION,
            access_codes=[],
            skill_sources=[],
        )
        workspace = TenantWorkspaceResolver(Config.DATA_DIR, tenant).resolve()
        return TenantContext.from_tenant_record(tenant, workspace)

    @property
    def tenant_manager(self):
        return self._registry.get(self.tenant_context)

    @property
    def encoder(self):
        return self.tenant_manager.encoder

    @property
    def qdrant_client(self):
        return self.tenant_manager.qdrant_client

    @property
    def route_manager(self):
        return self.tenant_manager.route_manager

    def is_ready(self) -> bool:
        try:
            self.ensure_ready()
            return True
        except Exception:
            return False

    def reinit_components(self):
        self._registry.clear(self.tenant_context.tenant_id)
        self.ensure_ready()

    def init_components(self, force: bool = False):
        if force:
            self._registry.clear(self.tenant_context.tenant_id)
        self.ensure_ready()

    def ensure_ready(self):
        self.tenant_manager.ensure_ready()


_component_manager: Optional[ComponentManager] = None


def get_component_manager() -> ComponentManager:
    """Return the singleton compatibility manager."""

    global _component_manager
    if _component_manager is None:
        _component_manager = ComponentManager()
    return _component_manager
