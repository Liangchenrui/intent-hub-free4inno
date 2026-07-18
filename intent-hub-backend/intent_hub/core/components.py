"""Lazy component container."""

from intent_hub.agent_store import AgentStore
from intent_hub.config import Config
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient


class ComponentManager:
    def __init__(self, encoder_factory=None, qdrant_client_factory=None, store=None):
        self.encoder_factory = encoder_factory or QwenEmbeddingEncoder
        self.qdrant_client_factory = qdrant_client_factory or IntentHubQdrantClient
        self.agent_store = store or AgentStore(Config.AGENTS_FILE)
        self._encoder = None
        self._qdrant_client = None

    @property
    def encoder(self):
        if self._encoder is None:
            self._encoder = self.encoder_factory(
                service_url=Config.EMBEDDING_SERVICE_URL,
                batch_size=Config.BATCH_SIZE,
            )
        return self._encoder

    @property
    def qdrant_client(self):
        if self._qdrant_client is None:
            self._qdrant_client = self.qdrant_client_factory(
                url=Config.QDRANT_URL,
                collection_name=Config.QDRANT_COLLECTION,
                dimensions=self.encoder.dimensions,
                api_key=Config.QDRANT_API_KEY,
            )
        return self._qdrant_client

    def reset_qdrant(self) -> None:
        self._qdrant_client = None


_component_manager = ComponentManager()


def get_component_manager() -> ComponentManager:
    return _component_manager
