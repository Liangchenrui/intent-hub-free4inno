"""Configuration generations with background warmup and request snapshots."""

import atexit
from threading import RLock, Thread
from time import monotonic
from types import SimpleNamespace

from intent_hub.config import Config
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.utils.logger import logger


class RoutingNotReady(RuntimeError):
    pass


class ComponentManager:
    def __init__(self, encoder_factory=None, qdrant_client_factory=None, route_manager_factory=None):
        self._encoder_factory = encoder_factory or QwenEmbeddingEncoder
        self._qdrant_client_factory = qdrant_client_factory or IntentHubQdrantClient
        self._route_manager_factory = route_manager_factory or RouteManager
        self._control = RLock()
        self._autowarm = False
        self._retired = []
        self._state = self._new_state()
        atexit.register(self.close)

    def _new_state(self):
        keys = ('EMBEDDING_SERVICE_URL', 'BATCH_SIZE', 'EMBEDDING_API_FORMAT', 'QDRANT_URL',
                'QDRANT_COLLECTION', 'QDRANT_API_KEY', 'QDRANT_TIMEOUT_SECONDS',
                'QDRANT_WRITE_BATCH_SIZE', 'ROUTES_CONFIG_PATH', 'SERVICE_HTTP_TRUST_ENV',
                'EMBEDDING_MODEL_NAME')
        return SimpleNamespace(lock=RLock(), encoder=None, qdrant_client=None, route_manager=None,
                               config={k: getattr(Config, k) for k in keys}, status='pending',
                               error_type=None, elapsed_ms=None, retry_after=0)

    def _get(self, state, name):
        value = getattr(state, name)
        if value is not None:
            return value
        with state.lock:
            value = getattr(state, name)
            if value is None:
                cfg = state.config
                if name == 'encoder':
                    value = self._encoder_factory(service_url=cfg['EMBEDDING_SERVICE_URL'],
                        batch_size=cfg['BATCH_SIZE'], api_format=cfg['EMBEDDING_API_FORMAT'],
                        trust_env=cfg['SERVICE_HTTP_TRUST_ENV'])
                elif name == 'qdrant_client':
                    value = self._qdrant_client_factory(url=cfg['QDRANT_URL'],
                        collection_name=cfg['QDRANT_COLLECTION'],
                        dimensions=self._get(state, 'encoder').dimensions,
                        api_key=cfg['QDRANT_API_KEY'], timeout=cfg['QDRANT_TIMEOUT_SECONDS'],
                        write_batch_size=cfg['QDRANT_WRITE_BATCH_SIZE'], trust_env=cfg['SERVICE_HTTP_TRUST_ENV'])
                else:
                    value = self._route_manager_factory(config_path=cfg['ROUTES_CONFIG_PATH'])
                setattr(state, name, value)
            return value

    encoder = property(lambda self: self._get(self._state, 'encoder'))
    qdrant_client = property(lambda self: self._get(self._state, 'qdrant_client'))
    route_manager = property(lambda self: self._get(self._state, 'route_manager'))
    # Preserve dependency injection used by local/offline integrations.
    _encoder = property(lambda self: self._state.encoder,
                        lambda self, value: setattr(self._state, 'encoder', value))
    _qdrant_client = property(lambda self: self._state.qdrant_client,
                             lambda self, value: setattr(self._state, 'qdrant_client', value))
    _route_manager = property(lambda self: self._state.route_manager,
                             lambda self, value: setattr(self._state, 'route_manager', value))

    @property
    def agent_store(self):
        from intent_hub.agent_store import AgentStore
        return AgentStore(self)

    def _prepare(self, state):
        started = monotonic()
        try:
            self._get(state, 'route_manager')
            self._get(state, 'qdrant_client')
            state.status = 'ready'
            state.error_type = None
        except Exception as exc:
            state.status = 'failed'
            state.error_type = type(exc).__name__
            state.retry_after = monotonic() + 5
            raise
        finally:
            state.elapsed_ms = round((monotonic() - started) * 1000, 3)

    def _warm_worker(self, state):
        try:
            self._prepare(state)
        except Exception:
            pass
        logger.info('Routing warmup status=%s elapsed_ms=%s error_type=%s',
                    state.status, state.elapsed_ms, state.error_type, extra={'category': 'system'})

    def start_warmup(self):
        with self._control:
            self._autowarm = True
            state = self._state
            if state.status in {'warming', 'ready'} or monotonic() < state.retry_after:
                return
            state.status = 'warming'
            Thread(target=self._warm_worker, args=(state,), name='routing-warmup', daemon=True).start()

    def readiness(self):
        state = self._state
        return {'status': state.status, 'error_type': state.error_type, 'elapsed_ms': state.elapsed_ms}

    def ready_snapshot(self):
        state = self._state
        if self._autowarm and state.status != 'ready':
            self.start_warmup()
            raise RoutingNotReady('Routing components are warming up or unavailable; retry shortly')
        if state.status != 'ready':
            self._prepare(state)
        return SimpleNamespace(encoder=state.encoder, qdrant_client=state.qdrant_client,
                               route_manager=state.route_manager, ensure_ready=lambda: None,
                               embedding_model_name=state.config['EMBEDDING_MODEL_NAME'])

    def ensure_ready(self):
        self._prepare(self._state)

    def is_ready(self):
        return self._state.status == 'ready'

    def reset_components(self):
        with self._control:
            self._retired.append(self._state)
            self._state = self._new_state()
            if self._autowarm:
                self.start_warmup()

    def reinit_components(self):
        self.reset_components()
        self.ensure_ready()

    def init_components(self, force=False):
        if force:
            self.reset_components()
        self.ensure_ready()

    def ensure_routes_ready(self):
        return self.route_manager

    def close(self):
        for state in [*self._retired, self._state]:
            for client in (state.encoder, getattr(state.qdrant_client, 'client', None)):
                close = getattr(client, 'close', None)
                if close:
                    close()


_component_manager = None
_manager_lock = RLock()


def get_component_manager():
    global _component_manager
    with _manager_lock:
        if _component_manager is None:
            _component_manager = ComponentManager()
        return _component_manager
