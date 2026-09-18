"""Migration, compatibility and recovery tests using isolated SQLite/Qdrant."""
import json
import sqlite3
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from intent_hub.app import app
from intent_hub import compat_api
from intent_hub.api import prediction
from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.migrate import migrate
from intent_hub.models import RouteConfig
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.repository import Repository
from intent_hub.route_manager import RouteManager
from intent_hub.services.route_service import RouteService
from intent_hub.services.sync_service import SyncService
from intent_hub.services.sync_task_service import SyncTaskService


def make_route(entity_id=1, key='orders'):
    return RouteConfig(id=entity_id, name=key, route_key=key, utterances=['track'], details={'id': 71, 'title': 'Orders'},
                       sync=RouteConfig.RouteSync(status='pending', version=1))


@pytest.fixture
def components(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'AUTH_ENABLED', True)
    monkeypatch.setattr(Config, 'AUTH_CODE', 'bupt-test-code')
    monkeypatch.setattr(Config, 'PREDICT_AUTH_KEY', 'master-test-code')
    monkeypatch.setattr(Config, 'SOURCE_INSTANCE', 'default')
    monkeypatch.setattr(Config, 'LLM_FALLBACK_ENABLED', False)
    monkeypatch.setattr(Config, 'QDRANT_COLLECTION', 'test')
    manager = ComponentManager()
    manager._route_manager = RouteManager(str(tmp_path / 'entities.sqlite3'))
    manager._encoder = SimpleNamespace(dimensions=2, encode_single=lambda text: [1., 0.], encode=lambda texts: [[1., 0.] for _ in texts])
    wrapper = object.__new__(IntentHubQdrantClient)
    wrapper.collection_name, wrapper.dimensions, wrapper.write_batch_size = 'test', 2, 32
    wrapper.client = QdrantClient(':memory:')
    wrapper.client.create_collection('test', vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    manager._qdrant_client = wrapper
    monkeypatch.setattr(compat_api, 'get_component_manager', lambda: manager)
    monkeypatch.setattr(prediction, 'get_component_manager', lambda: manager)
    yield manager
    wrapper.client.close()


def test_both_prediction_contracts_share_sqlite_and_vectors(components):
    components.route_manager.add_route(make_route())
    SyncService(components).sync_route(1)
    client = app.test_client()
    master = client.post('/compat/master/predict', json={'text': 'track'}, headers={'Authorization': 'Bearer master-test-code'})
    bupt = client.post('/compat/bupt/route', json={'query': 'track'}, headers={'Authorization': 'Bearer bupt-test-code'})
    assert master.status_code == bupt.status_code == 200
    assert master.json[0]['route_key'] == 'orders'
    assert bupt.json == {'success': True, 'error': None, 'data': {'matched': True, 'agents': [{'agent': {'id': 71, 'title': 'Orders'}, 'score': 1.0}], 'text': None, 'match_source': 'semantic', 'fallback_status': None}}


@pytest.mark.parametrize('path,payload,wrong', [('/compat/master/predict', {'text': 'track'}, 'bupt-test-code'), ('/compat/bupt/route', {'query': 'track'}, 'master-test-code')])
def test_auth_does_not_cross_contracts(components, path, payload, wrong):
    client = app.test_client()
    assert client.post(path, json=payload).status_code == 401
    assert client.post(path, json=payload, headers={'Authorization': 'Bearer ' + wrong}).status_code == 401


def test_negative_local_id_is_editable_and_deleted_entity_is_not_routed(components):
    client = app.test_client()
    headers = {'Authorization': 'Bearer bupt-test-code'}
    created = client.post('/compat/bupt/agents', json={'title': 'Local', 'utterances': ['track']}, headers=headers)
    assert created.status_code == 201
    legacy_id = created.json['id']
    assert legacy_id < 0
    entity_id = components.agent_store.internal_id(legacy_id)
    SyncService(components).sync_route(entity_id)
    updated = client.patch(f'/compat/bupt/agents/{legacy_id}', json={'text': 'new description'}, headers=headers)
    assert updated.status_code == 200 and updated.json['text'] == 'new description'
    assert client.delete(f'/compat/bupt/agents/{legacy_id}', headers=headers).status_code == 200
    routed = client.post('/compat/bupt/route', json={'query': 'track'}, headers=headers)
    assert routed.json['data']['matched'] is False


def test_merge_is_atomic_and_preserves_originals(components):
    left = components.agent_store.create_local(title='Left', utterances=['one'], negative_samples=['x'])
    right = components.agent_store.create_local(title='Right', utterances=['two'], negative_samples=['y'])
    merged = components.agent_store.merge(left.id, right.id, 'Combined', '')
    assert merged.utterances == ['one', 'two']
    assert merged.negative_samples == ['x', 'y']
    assert components.agent_store.get(left.id).lifecycle_status == 'inactive'
    assert len(components.route_manager.repository.pending()) == 3
    before = len(components.agent_store.all())
    with pytest.raises(ValueError):
        components.agent_store.merge(merged.id, merged.id, 'bad', '')
    assert len(components.agent_store.all()) == before


def test_master_migration_dry_run_idempotence_and_source_preservation(tmp_path):
    source, target = tmp_path / 'routes.json', tmp_path / 'unified.sqlite3'
    route = make_route()
    source.write_text(json.dumps([route.model_dump()]), encoding='utf-8')
    original = source.read_bytes()
    assert migrate(source, target)['mode'] == 'dry-run'
    assert not target.exists()
    migrate(source, target, apply=True)
    assert Repository(target).all()[0].model_dump() == route.model_dump()
    assert migrate(source, target, apply=True)['already_applied']
    assert source.read_bytes() == original
    source.write_text('[]', encoding='utf-8')
    with pytest.raises(ValueError, match='Source changed'):
        migrate(source, target, apply=True)
    assert len(Repository(target).all()) == 1


def test_migration_duplicate_key_does_not_create_target(tmp_path):
    source, target = tmp_path / 'routes.json', tmp_path / 'unified.sqlite3'
    source.write_text(json.dumps([make_route().model_dump(), make_route(2).model_dump()]))
    with pytest.raises(ValueError, match='Duplicate'):
        migrate(source, target, apply=True)
    assert not target.exists()


def test_bupt_sqlite_migration_preserves_fields_and_aliases(tmp_path):
    source, target = tmp_path / 'agents.sqlite3', tmp_path / 'unified.sqlite3'
    with sqlite3.connect(source) as db:
        db.execute('CREATE TABLE agents (id INTEGER, title TEXT, text TEXT, utterances TEXT, negative_samples TEXT, score_threshold REAL, negative_threshold REAL, details TEXT, source_type TEXT, upstream_id INTEGER, upstream_present INTEGER, manual_overrides TEXT, source_snapshot TEXT, lifecycle_status TEXT)')
        db.execute('INSERT INTO agents VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', (-4, 'Local', 'desc', '["one"]', '["no"]', .82, .96, '{"a":1}', 'local', None, None, '["title"]', '{"title":"old"}', 'inactive'))
    migrate(source, target, 'bupt', 'campus', True)
    repo = Repository(target)
    route = repo.all()[0]
    assert route.id > 0 and repo.resolve('bupt', 'campus', -4) == route.id
    assert (route.name, route.description, route.lifecycle_status, route.score_threshold, route.negative_threshold) == ('Local', 'desc', 'disabled', .82, .96)
    assert route.details == {'a': 1} and route.source.source_snapshot == {'name': 'old'}
    assert route.sync.manual_overrides == ['name']
    assert migrate(source, target, 'bupt', 'campus', True)['already_applied']


def test_outbox_survives_restart_and_deletion_without_api_enqueue(components):
    manager = components.route_manager
    manager.add_route(make_route())
    manager.delete_route(1)
    queue = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    assert queue.list_tasks()[0]['route_ids'] == [1]
    assert queue.process_next()
    reopened = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    assert reopened.list_tasks()[0]['status'] == 'succeeded'


def test_task_target_change_never_writes_to_new_collection(components, monkeypatch):
    components.route_manager.add_route(make_route())
    queue = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    monkeypatch.setattr(Config, 'QDRANT_COLLECTION', 'other')
    queue.process_next()
    assert queue.list_tasks()[0]['status'] == 'superseded'
    assert components.qdrant_client.index_summary()['points_count'] == 0


def test_bupt_sync_completion_uses_shared_task_executor(components, monkeypatch):
    import intent_hub.compat_services as services
    components.route_manager.add_route(make_route())
    queue = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    original = queue.list_tasks
    def progress(*args, **kwargs):
        queue.process_next()
        return original(*args, **kwargs)
    monkeypatch.setattr(queue, 'list_tasks', progress)
    monkeypatch.setattr(services, 'get_sync_task_service', lambda _: queue)
    result = services.SyncService(components).sync()
    assert result['agents_count'] == 1 and result['description_points'] == 1
    assert services.SyncService(components).status()['synced']


def test_secrets_rejected_and_not_returned(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(tmp_path / 'settings.json'))
    for key in Config.SECRET_KEYS:
        assert key not in Config.to_dict()
        with pytest.raises(ValueError, match='startup-only'):
            Config.save({key: 'must-not-persist'})
    assert not (tmp_path / 'settings.json').exists()


def test_failure_rolls_back_entity_and_outbox_transaction(components):
    repo = components.route_manager.repository
    with pytest.raises(RuntimeError):
        with repo.transaction() as db:
            repo.save(make_route(), db)
            raise RuntimeError('interrupted')
    assert repo.all() == [] and repo.pending() == []


def test_bupt_alias_collision_keeps_both_entities_addressable(components):
    repo = components.route_manager.repository
    with repo.transaction() as db:
        repo.save(make_route(1, 'master'), db)
        repo.save(make_route(2, 'bupt'), db)
        repo.bind('bupt', 'default', 1, 2, db)
    store = components.agent_store
    agents = store.all()
    assert len({a.id for a in agents}) == 2
    for agent in agents:
        assert store.get(agent.id).title == agent.title


def test_bupt_settings_has_its_original_field_set(components):
    from intent_hub.compat_config import KEYS
    response = app.test_client().get('/compat/bupt/settings', headers={'Authorization': 'Bearer bupt-test-code'})
    assert response.status_code == 200 and set(response.json) == KEYS


def test_failed_settings_write_does_not_mutate_effective_config(tmp_path, monkeypatch):
    import os
    old = Config.LLM_MODEL
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(tmp_path / 'settings.json'))
    def fail(*args):
        raise OSError('simulated disk error')
    monkeypatch.setattr(os, 'replace', fail)
    with pytest.raises(OSError):
        Config.save({'LLM_MODEL': 'should-not-be-applied'})
    assert Config.LLM_MODEL == old


def test_bupt_profile_selects_root_contract_without_changing_master_namespace(tmp_path):
    import os
    import subprocess
    import sys
    env = {**os.environ, 'API_COMPAT_PROFILE': 'bupt', 'AUTH_CODE': 'bupt-test-code',
           'INTENT_HUB_DATA_DIR': str(tmp_path), 'PYTHONPATH': str(__import__('pathlib').Path(__file__).resolve().parents[1])}
    code = '''from intent_hub.app import app
from intent_hub.compat_config import KEYS
c=app.test_client()
r=c.get('/settings',headers={'Authorization':'Bearer bupt-test-code'})
assert r.status_code==200 and set(r.json)==KEYS
assert c.get('/compat/master/settings',headers={'Authorization':'Bearer bupt-test-code'}).status_code==401
from intent_hub import compat_api
from types import SimpleNamespace
compat_api.DiagnosticService=lambda _: SimpleNamespace(analyze_route=lambda n: SimpleNamespace(model_dump=lambda: {'bupt_id':n}))
compat_api.get_component_manager=lambda: None
for n in [7,-7]:
    r=c.get('/diagnostics/overlap/'+str(n),headers={'Authorization':'Bearer bupt-test-code'})
    assert r.status_code==200 and r.json=={'bupt_id':n}
'''
    subprocess.run([sys.executable, '-c', code], env=env, check=True, timeout=60, capture_output=True)


@pytest.mark.parametrize('decision,expected', [('matched', True), ('ambiguous', False), ('no_match', False)])
def test_bupt_fallback_uses_shared_classifier_and_null_score(components, monkeypatch, decision, expected):
    from intent_hub.services.fallback_service import FallbackService, FallbackDecision
    components.route_manager.add_route(make_route())
    SyncService(components).sync_route(1)
    monkeypatch.setattr(Config, 'LLM_FALLBACK_ENABLED', True)
    monkeypatch.setattr(components.qdrant_client, 'search', lambda *a, **k: [])
    monkeypatch.setattr(FallbackService, '_classify', lambda *a: FallbackDecision(status=decision, route_id=1 if expected else None))
    response = app.test_client().post('/compat/bupt/route', json={'query': 'track'}, headers={'Authorization': 'Bearer bupt-test-code'})
    assert response.status_code == 200
    data = response.json['data']
    assert data['matched'] == expected and data['fallback_status'] == decision
    if expected:
        assert data['agents'][0]['score'] is None and data['match_source'] == 'llm_fallback'
    else:
        assert data['agents'] == [] and data['text'] == Config.DEFAULT_ROUTE_TEXT


def test_multimatch_and_negative_exclusion_on_both_contracts(components):
    for i in (1, 2, 3):
        route = make_route(i, f'orders{i}')
        if i == 3:
            route.negative_samples = ['track']
        components.route_manager.add_route(route)
        SyncService(components).sync_route(i)
    client = app.test_client()
    master = client.post('/compat/master/predict', json={'text': 'track'}, headers={'Authorization': 'Bearer master-test-code'})
    bupt = client.post('/compat/bupt/route', json={'query': 'track'}, headers={'Authorization': 'Bearer bupt-test-code'})
    assert {r['id'] for r in master.json} == {1, 2}
    assert len(bupt.json['data']['agents']) == 2


def test_packaging_excludes_runtime_and_frontend_does_not_inject_credentials():
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    ignore = (root / 'intent-hub-backend/.dockerignore').read_text()
    assert 'data/*' in ignore and '.env' in ignore
    nginx = (root / 'intent-hub-frontend/nginx.conf').read_text(encoding='utf-8')
    assert 'Bearer ${INTENT_HUB_AUTH_CODE}' not in nginx


def test_old_task_save_cannot_consume_later_delete_intent(components):
    route = make_route()
    route.sync = None
    manager = components.route_manager
    manager.add_route(route)
    queue = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    queue.process_next()
    manager.delete_route(route.id)
    queue._save_tasks()  # An unrelated completion persists the old task snapshot.
    assert manager.repository.pending() == [route.id]
    restarted = SyncTaskService(components, autostart=False, refresh_diagnostics=False)
    restarted.process_next()
    assert components.qdrant_client.index_summary()['points_count'] == 0


def test_collection_restore_uses_alias_and_preserves_details(components, monkeypatch):
    from intent_hub.compat_services import CollectionService
    from intent_hub.services.qdrant_import_service import QdrantImportService
    components.route_manager.add_route(make_route(1, 'master'))
    components.route_manager.add_route(make_route(2, 'bupt'))
    with components.route_manager.repository.transaction() as db:
        components.route_manager.repository.bind('bupt', 'default', 1, 2, db)
    points = [{'payload': {'route_id': 1, 'route_name': 'Restored', 'utterance': 'restored sample'}}]
    monkeypatch.setattr(QdrantImportService, '_scroll_payloads', lambda *args: points)
    monkeypatch.setattr(Config, 'save', lambda values: None)
    monkeypatch.setattr(components, 'reset_components', lambda: None)
    result = CollectionService(components).restore_collection('legacy')
    assert result['restored_agents'] == 1
    assert components.route_manager.get_route(1).name == 'master'
    restored = components.route_manager.get_route(2)
    assert restored.name == 'Restored'
    assert restored.details == {'id': 71, 'title': 'Orders'}
    assert restored.route_key == 'bupt'
    assert restored.sync.status == 'pending'


def test_upstream_pull_does_not_reactivate_merged_originals(components):
    from intent_hub.services.upstream_agent_service import UpstreamAgentService
    incoming = [dict(source_id=str(i), name=f'Agent {i}', description='', utterances=['track'], negative_samples=[]) for i in (1, 2)]
    source = SimpleNamespace(fetch_all=lambda: incoming)
    UpstreamAgentService(components, source).pull()
    originals = components.agent_store.all()
    components.agent_store.merge(originals[0].id, originals[1].id, 'Merged', '')
    UpstreamAgentService(components, source).pull()
    assert all(components.agent_store.get(a.id).lifecycle_status == 'inactive' for a in originals)
    assert len(components.agent_store.active()) == 1
