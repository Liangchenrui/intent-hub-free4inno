"""Tenant-scoped component managers."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from intent_hub.config import Config
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.tenant.context import TenantContext


class TenantComponentManager:
    """Initialize and hold runtime components for one tenant."""

    def __init__(
        self,
        context: TenantContext,
        encoder_factory: Callable[..., object] | None = None,
        qdrant_client_factory: Callable[..., object] | None = None,
        route_manager_factory: Callable[..., object] | None = None,
    ):
        self.context = context
        self._encoder_factory = encoder_factory or QwenEmbeddingEncoder
        self._qdrant_client_factory = qdrant_client_factory or IntentHubQdrantClient
        self._route_manager_factory = route_manager_factory or RouteManager

        self._encoder = None
        self._qdrant_client = None
        self._route_manager = None
        self._settings_cache: dict[str, Any] | None = None

    def _load_tenant_settings(self) -> dict[str, Any]:
        if self._settings_cache is not None:
            return self._settings_cache

        defaults = Config.to_dict()
        settings_path = Path(self.context.settings_path)
        if not settings_path.exists():
            self._settings_cache = defaults
            return self._settings_cache

        try:
            payload = json.loads(settings_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                merged = dict(defaults)
                merged.update(payload)
                self._settings_cache = merged
                return self._settings_cache
        except Exception:
            pass

        self._settings_cache = defaults
        return self._settings_cache

    def get_setting(self, key: str, default: Any = None) -> Any:
        settings = self._load_tenant_settings()
        if key in settings:
            return settings[key]
        return default

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = self._encoder_factory(
                service_url=self.get_setting("EMBEDDING_SERVICE_URL", Config.EMBEDDING_SERVICE_URL),
                batch_size=self.get_setting("BATCH_SIZE", Config.BATCH_SIZE),
            )
        return self._encoder

    @property
    def qdrant_client(self):
        if self._qdrant_client is None:
            self._qdrant_client = self._qdrant_client_factory(
                url=self.get_setting("QDRANT_URL", Config.QDRANT_URL),
                collection_name=self.context.collection_name,
                dimensions=self.encoder.dimensions,
                api_key=self.get_setting("QDRANT_API_KEY", Config.QDRANT_API_KEY),
            )
        return self._qdrant_client

    @property
    def route_manager(self):
        if self._route_manager is None:
            self._route_manager = self._route_manager_factory(
                config_path=str(self.context.routes_path)
            )
        return self._route_manager

    def ensure_ready(self) -> None:
        _ = self.route_manager
        _ = self.qdrant_client


class TenantComponentRegistry:
    """Cache tenant component managers by tenant_id."""

    def __init__(
        self,
        encoder_factory: Callable[..., object] | None = None,
        qdrant_client_factory: Callable[..., object] | None = None,
        route_manager_factory: Callable[..., object] | None = None,
    ):
        self._encoder_factory = encoder_factory
        self._qdrant_client_factory = qdrant_client_factory
        self._route_manager_factory = route_manager_factory
        self._managers: dict[str, TenantComponentManager] = {}

    def get(self, context: TenantContext) -> TenantComponentManager:
        manager = self._managers.get(context.tenant_id)
        if manager is None:
            manager = TenantComponentManager(
                context=context,
                encoder_factory=self._encoder_factory,
                qdrant_client_factory=self._qdrant_client_factory,
                route_manager_factory=self._route_manager_factory,
            )
            self._managers[context.tenant_id] = manager
        return manager

    def clear(self, tenant_id: str | None = None) -> None:
        if tenant_id is None:
            self._managers.clear()
            return
        self._managers.pop(tenant_id, None)
