"""Latency mechanisms tested without relying on remote service speed."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event, Lock
from types import SimpleNamespace
from time import monotonic

import pytest
from flask import Flask, g

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.encoder import QwenEmbeddingEncoder
from intent_hub.services.llm_factory import LLMFactory
from intent_hub.services.llm_runtime import LLMRuntime
from intent_hub.utils.route_trace import run_parallel_searches


def wait_ready(manager):
    from time import sleep
    deadline = monotonic() + 3
    while manager.readiness()['status'] == 'warming' and monotonic() < deadline:
        sleep(.005)
    assert manager.readiness()['status'] == 'ready'


def test_warmup_single_initialization_fast_gate_and_configuration_generation(monkeypatch):
    entered, release = Event(), Event()
    counts = []
    def qdrant(**kwargs):
        counts.append(kwargs['collection_name'])
        if len(counts) == 1:
            entered.set()
            assert release.wait(3)
        return SimpleNamespace(collection_name=kwargs['collection_name'])
    manager = ComponentManager(encoder_factory=lambda **kw: SimpleNamespace(dimensions=2),
        qdrant_client_factory=qdrant, route_manager_factory=lambda **kw: object())
    manager.ensure_routes_ready()
    manager.start_warmup()
    assert entered.wait(2)
    for _ in range(5):
        manager.start_warmup()
    with pytest.raises(RuntimeError, match='warming'):
        manager.ready_snapshot()
    # Existing local storage is accessible even while remote initialization blocks.
    assert manager.ensure_routes_ready() is not None
    monkeypatch.setattr(Config, 'QDRANT_COLLECTION', 'new-generation')
    manager.reset_components()
    wait_ready(manager)
    snapshot = manager.ready_snapshot()
    assert snapshot.qdrant_client.collection_name == 'new-generation'
    release.set()
    assert len(counts) == 2
    assert manager.ready_snapshot().qdrant_client is snapshot.qdrant_client


def test_parallel_searches_overlap_and_keep_request_evidence():
    barrier = Barrier(2)
    def search(value):
        barrier.wait(timeout=2)
        return value
    with Flask(__name__).test_request_context():
        g.log_started = monotonic()
        assert run_parallel_searches(lambda: search('negative'), lambda: search('positive')) == ('negative', 'positive')
        spans = {s['stage']: s for s in g.route_timings}
        a, b = spans['negative_search'], spans['positive_search']
        assert max(a['offset_ms'], b['offset_ms']) < min(a['offset_ms'] + a['elapsed_ms'], b['offset_ms'] + b['elapsed_ms'])
        assert all(s['status'] == 'succeeded' for s in spans.values())


def test_parallel_failure_waits_for_other_worker_and_records_failure():
    barrier = Barrier(2)
    finished = Event()
    def fail():
        barrier.wait(timeout=2)
        raise ValueError('failed')
    def finish():
        barrier.wait(timeout=2)
        finished.set()
        return []
    with Flask(__name__).test_request_context():
        g.log_started = monotonic()
        with pytest.raises(ValueError):
            run_parallel_searches(fail, finish)
        assert finished.is_set()
        assert next(s for s in g.route_timings if s['stage'] == 'negative_search')['status'] == 'failed'
        assert all('elapsed_ms' in s for s in g.route_timings)


def test_llm_reuse_config_switch_and_inflight_retirement(monkeypatch):
    clients, loops = [], []
    entered, release = Event(), Event()
    class Model:
        async def ainvoke(self, messages):
            loops.append(asyncio.get_running_loop())
            if messages == ['hold']:
                entered.set()
                while not release.is_set():
                    await asyncio.sleep(.005)
            return 'ok'
    def create(**options):
        clients.append(options['http_async_client'])
        return Model()
    monkeypatch.setattr(LLMFactory, 'create_llm', create)
    monkeypatch.setattr(Config, 'LLM_PROVIDER', 'deepseek')
    runtime = LLMRuntime()
    try:
        assert runtime.invoke(['first']) == runtime.invoke(['second']) == 'ok'
        assert len(clients) == 1 and not clients[0].is_closed
        with ThreadPoolExecutor(1) as pool:
            active = pool.submit(runtime.invoke, ['hold'])
            assert entered.wait(2)
            monkeypatch.setattr(Config, 'LLM_MODEL', 'changed-model')
            assert runtime.invoke(['new']) == 'ok'
            assert len(clients) == 2 and not clients[0].is_closed
            release.set()
            assert active.result(timeout=2) == 'ok'
        assert clients[0].is_closed and not clients[1].is_closed
        assert all(loop is runtime.loop for loop in loops)
    finally:
        release.set()
        runtime.close()
    assert all(client.is_closed for client in clients)


def test_embedding_http_keepalive_cache_and_copy_isolation(monkeypatch):
    import json
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread
    peers = []
    class Handler(BaseHTTPRequestHandler):
        protocol_version = 'HTTP/1.1'
        def log_message(self, *_):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            peers.append(self.client_address)
            body = json.dumps([[1., 0.] for _ in payload['inputs']]).encode()
            self.send_response(200)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv('NO_PROXY', '127.0.0.1,localhost')
    encoder = QwenEmbeddingEncoder(f'http://127.0.0.1:{server.server_port}/embed', api_format='tei')
    try:
        value = encoder.encode_single('query')
        value[0] = 99
        assert encoder.encode_single('query') == [1., 0.]
        assert len(peers) == 2 and peers[0] == peers[1]
        encoder._cache_limit = 2
        for text in ('a', 'b', 'c'):
            encoder.encode_single(text)
        assert len(encoder._cache) == 2 and 'query' not in encoder._cache
    finally:
        encoder.close()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_qdrant_server_time_extracted_without_response_payload():
    import httpx
    from intent_hub.qdrant_wrapper import _capture_server_time, _server_time
    from intent_hub.utils.route_trace import remote_timing
    with Flask(__name__).test_request_context():
        _capture_server_time(httpx.Response(200, json={'time': .002, 'result': {'secret': 'hidden'}}))
        remote_timing('qdrant', 123, _server_time.get())
        assert g.route_events[0]['server_ms'] == 2
        assert 'secret' not in str(g.route_events)


def test_failed_warmup_can_retry_and_health_does_not_report_ready(monkeypatch):
    from intent_hub.app import app
    from time import sleep
    attempts = []
    def factory(**kw):
        attempts.append(True)
        if len(attempts) == 1:
            raise RuntimeError('unavailable')
        return object()
    manager = ComponentManager(encoder_factory=lambda **kw: SimpleNamespace(dimensions=2),
        qdrant_client_factory=factory, route_manager_factory=lambda **kw: object())
    monkeypatch.setattr('intent_hub.app.get_component_manager', lambda: manager)
    client = app.test_client()
    assert client.get('/health').status_code == 200
    client.get('/health/ready')
    deadline = monotonic() + 2
    while manager.readiness()['status'] == 'warming' and monotonic() < deadline:
        sleep(.005)
    assert client.get('/health/ready').status_code == 503
    manager._state.retry_after = 0
    client.get('/health/ready')
    wait_ready(manager)
    assert client.get('/health/ready').status_code == 200


def test_prediction_contracts_return_503_during_warmup(monkeypatch):
    from intent_hub.app import app
    from intent_hub.core.components import RoutingNotReady
    def not_ready():
        raise RoutingNotReady('Routing components are warming up')
    manager = SimpleNamespace(ready_snapshot=not_ready)
    monkeypatch.setattr('intent_hub.api.prediction.get_component_manager', lambda: manager)
    monkeypatch.setattr('intent_hub.compat_api.get_component_manager', lambda: manager)
    monkeypatch.setattr(Config, 'AUTH_ENABLED', False)
    monkeypatch.setattr(Config, 'PREDICT_AUTH_KEY', '')
    monkeypatch.setattr(Config, 'AUTH_CODE', 'offline-test')
    client = app.test_client()
    assert client.post('/compat/master/predict', json={'text': 'query'}).status_code == 503
    result = client.post('/compat/bupt/route', json={'query': 'query'},
                         headers={'Authorization': 'Bearer offline-test'})
    assert result.status_code == 503
    assert result.json['error']['code'] == 'SERVICE_NOT_READY'


@pytest.mark.parametrize('trust_env', [True, False])
def test_management_http_honors_service_environment_policy(monkeypatch, trust_env):
    from intent_hub.utils import service_http
    seen = []
    class Session:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            seen.append('closed')
        def request(self, method, url, **kwargs):
            seen.append((self.trust_env, method, url, kwargs))
            return 'response'
    monkeypatch.setattr(service_http._requests, 'Session', Session)
    monkeypatch.setattr(Config, 'SERVICE_HTTP_TRUST_ENV', trust_env)
    assert service_http.get('https://service/health', timeout=5) == 'response'
    assert seen == [(trust_env, 'GET', 'https://service/health', {'timeout': 5}), 'closed']
