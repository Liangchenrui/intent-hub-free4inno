"""Single-workspace component management."""

from typing import Optional

from intent_hub.config import Config
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager


class ComponentManager:
    """Lazily build the components shared by the single Intent Hub workspace."""

    def __init__(
        self,
        encoder_factory=None,
        qdrant_client_factory=None,
        route_manager_factory=None,
    ):
        self._encoder_factory = encoder_factory or QwenEmbeddingEncoder
        self._qdrant_client_factory = qdrant_client_factory or IntentHubQdrantClient
        self._route_manager_factory = route_manager_factory or RouteManager
        self._encoder = None
        self._qdrant_client = None
        self._route_manager = None

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = self._encoder_factory(
                service_url=Config.EMBEDDING_SERVICE_URL,
                batch_size=Config.BATCH_SIZE,
                api_format=Config.EMBEDDING_API_FORMAT,
            )
        return self._encoder

    @property
    def qdrant_client(self):
        if self._qdrant_client is None:
            self._qdrant_client = self._qdrant_client_factory(
                url=Config.QDRANT_URL,
                collection_name=Config.QDRANT_COLLECTION,
                dimensions=self.encoder.dimensions,
                api_key=Config.QDRANT_API_KEY,
                timeout=Config.QDRANT_TIMEOUT_SECONDS,
                write_batch_size=Config.QDRANT_WRITE_BATCH_SIZE,
            )
        return self._qdrant_client

    @property
    def route_manager(self):
        if self._route_manager is None:
            self._route_manager = self._route_manager_factory(
                config_path=Config.ROUTES_CONFIG_PATH
            )
        return self._route_manager

    def is_ready(self) -> bool:
        try:
            self.ensure_ready()
            return True
        except Exception:
            return False

    def reinit_components(self):
        self.reset_components()
        self.ensure_ready()

    def reset_components(self):
        """Drop cached components so they are rebuilt lazily on the next use."""
        self._encoder = None
        self._qdrant_client = None
        self._route_manager = None

    def init_components(self, force: bool = False):
        if force:
            self._encoder = None
            self._qdrant_client = None
            self._route_manager = None
        self.ensure_ready()

    def ensure_ready(self):
        _ = self.route_manager
        _ = self.qdrant_client

    def ensure_routes_ready(self):
        """Initialize only local route storage; never touch remote services."""
        return self.route_manager


_component_manager: Optional[ComponentManager] = None


def get_component_manager() -> ComponentManager:
    global _component_manager
    if _component_manager is None:
        _component_manager = ComponentManager()
    return _component_manager
