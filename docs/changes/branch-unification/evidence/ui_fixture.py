"""Local-only UI fixture: real SQLite/Qdrant, deterministic LLM/health stubs.

Run from the repository root with python; serves 127.0.0.1:5188.
Credentials are synthetic fixture data, never valid outside this fixture.
"""
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[4]
os.environ['INTENT_HUB_DATA_DIR'] = tempfile.mkdtemp(prefix='intent-hub-ui-')
os.environ['DEFAULT_PASSWORD'] = 'fixture-password'
os.environ['AUTH_CODE'] = 'fixture-bupt-code'
sys.path.insert(0, str(ROOT / 'intent-hub-backend'))

from flask import Flask, send_from_directory
from werkzeug.middleware.dispatcher import DispatcherMiddleware
from werkzeug.serving import run_simple
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.core import components
from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.services.sync_service import SyncService
from intent_hub.services.llm_service import LLMService
from intent_hub.services import health_service

manager = components.ComponentManager()
manager._route_manager = RouteManager(str(Path(Config.DATA_DIR) / 'entities.sqlite3'))
manager._encoder = SimpleNamespace(dimensions=2, encode=lambda texts: [[1., 0.] for _ in texts], encode_single=lambda text: [1., 0.])
wrapper = object.__new__(IntentHubQdrantClient)
wrapper.collection_name, wrapper.dimensions, wrapper.write_batch_size = 'fixture', 2, 32
wrapper.client = QdrantClient(':memory:')
wrapper.client.create_collection('fixture', vectors_config=VectorParams(size=2, distance=Distance.COSINE))
manager._qdrant_client = wrapper
components._component_manager = manager
Config.QDRANT_COLLECTION = 'fixture'
Config.LLM_FALLBACK_ENABLED = False
for entity_id, name in [(1, '订单查询'), (2, '物流查询')]:
    manager.route_manager.add_route(RouteConfig(id=entity_id, name=name, route_key=f'fixture.{entity_id}', description='离线界面验证数据', utterances=['查询订单状态']))
    SyncService(manager).sync_route(entity_id)
LLMService.recommendations = lambda *args: ['取消订单', '修改收货地址']
health_service.check_external_services = lambda: {'status': 'ok', 'services': {}}

frontend = Flask('fixture_frontend', static_folder=None)
dist = ROOT / 'intent-hub-frontend/dist'


@frontend.get('/')
@frontend.get('/<path:path>')
def page(path=''):
    if path.startswith('assets/'):
        return send_from_directory(dist, path)
    return send_from_directory(dist, 'index.html')


if __name__ == '__main__':
    run_simple('127.0.0.1', 5188, DispatcherMiddleware(frontend, {'/api': app}), threaded=True)
