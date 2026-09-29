from types import SimpleNamespace

import pytest

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager
from intent_hub.services.upstream_agent_service import UpstreamAgentService
from intent_hub.services.sync_task_service import SyncTaskService
from intent_hub.upstreams import bindings, route_key, validate_upstreams


def source(identity, name):
    return dict(id=identity, name=name, url=f'https://{name}.test/api', label_ids='1,2')


def item(identity='123', name='Agent'):
    return dict(source_id=identity, route_key='ignored.key', name=name, description='remote',
                utterances=['hello'], negative_samples=[])


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPSTREAMS', [source('default', 'default'), source('b', 'partner')])
    monkeypatch.setattr(Config, 'SOURCE_INSTANCE', 'default')
    monkeypatch.setattr(Config, 'SETTINGS_FILE_PATH', str(tmp_path / 'settings.json'))
    return SimpleNamespace(route_manager=RouteManager(str(tmp_path / 'routes.sqlite3')))


def pull(system, identity='default', items=None, **attributes):
    adapter = SimpleNamespace(fetch_all=lambda: [item()] if items is None else items, **attributes)
    return UpstreamAgentService(system, adapter, upstream_id=identity).pull()


def test_sources_are_isolated_and_repeat_pull_is_idempotent(system):
    pull(system)
    pull(system, 'b')
    routes = system.route_manager.get_all_routes()
    assert {r.route_key for r in routes} == {'default.123', 'partner.123'}
    assert pull(system)['unchanged'] == 1
    assert pull(system, items=[item('456')])['upstream_missing'] == 1
    partner = next(r for r in system.route_manager.get_all_routes() if r.source.instance == 'b')
    assert partner.lifecycle_status == 'active'
    assert partner == routes[1]
    assert pull(system, 'b')['routes_count'] == 1


def test_same_names_and_upstream_keys_with_different_ids_remain_distinct(system):
    assert pull(system, items=[item('1'), item('2')])['created'] == 2
    assert {r.route_key for r in system.route_manager.get_all_routes()} == {'default.1', 'default.2'}


def test_identity_encoding_does_not_collapse_case_or_punctuation():
    ids = ['A', 'a', 'x.y', 'x..y', 'x y', 'x%20y', '123', '中文']
    keys = [route_key('default', i) for i in ids]
    assert len(set(keys)) == len(ids)
    assert all(RouteManager.normalize_route_key(key) == key for key in keys)
    assert route_key('default', 123) == 'default.123'


@pytest.mark.parametrize('identity', [None, '', ' ', False])
def test_missing_id_rejects_entire_batch(system, identity):
    with pytest.raises(ValueError, match='原始 ID'):
        pull(system, items=[item('good'), item(identity)])
    assert system.route_manager.get_all_routes() == []
    assert bindings(system.route_manager.repository) == {}


def test_collision_with_manual_route_rolls_back_batch(system):
    repo = system.route_manager.repository
    manual = RouteConfig(id=7, name='Manual', route_key='default.123', utterances=['manual'])
    repo.save(manual, enqueue=False)
    with pytest.raises(ValueError, match='冲突'):
        pull(system, items=[item('new'), item()])
    assert repo.all() == [manual]
    assert repo.pending() == []


def test_config_change_during_fetch_discards_batch(system, monkeypatch):
    def fetch():
        monkeypatch.setattr(Config, 'UPSTREAMS', [source('default', 'changed'), source('b', 'partner')])
        return [item()]
    with pytest.raises(ValueError, match='配置已变更'):
        UpstreamAgentService(system, SimpleNamespace(fetch_all=fetch)).pull()
    assert system.route_manager.get_all_routes() == []


def test_other_source_change_does_not_cancel_pull(system, monkeypatch):
    def fetch():
        monkeypatch.setattr(Config, 'UPSTREAMS', [source('default', 'default'), source('b', 'other')])
        return [item()]
    assert UpstreamAgentService(system, SimpleNamespace(fetch_all=fetch)).pull()['created'] == 1


def test_task_deduplication_and_removed_source(system, monkeypatch):
    queue = SyncTaskService(system, autostart=False, refresh_diagnostics=False)
    first = queue.enqueue_upstream_pull('default')
    assert queue.enqueue_upstream_pull('default')['id'] == first['id']
    second = queue.enqueue_upstream_pull('b')
    assert first['id'] != second['id']
    monkeypatch.setattr(Config, 'UPSTREAMS', [source('b', 'partner')])
    assert queue.process_next()
    assert queue.list_tasks()[0]['status'] == 'superseded'


def test_name_lock_persists_and_cannot_be_bypassed_by_api(system, monkeypatch):
    from intent_hub.app import app
    from intent_hub.api import settings
    monkeypatch.setattr('intent_hub.core.components.get_component_manager', lambda: system)
    pull(system, items=[])
    assert bindings(RouteManager(system.route_manager.config_path).repository)['default'] == 'default'
    with app.test_request_context(json={'UPSTREAMS': [source('default', 'renamed')]}):
        response, status = settings.update_settings()
    assert status == 400
    assert '名称不可修改' in response.get_json()['detail']
    assert Config.get_upstreams()[0]['name'] == 'default'
    # Removing configuration preserves data/ownership; a new identity cannot reuse it.
    with app.test_request_context(json={'UPSTREAMS': [source('new-id', 'default')]}):
        assert settings.update_settings()[1] == 400


def test_save_multiple_sources_and_reload(system, monkeypatch):
    for key in Config.to_dict():
        monkeypatch.setattr(Config, key, getattr(Config, key))
    Config.save({'UPSTREAMS': [source('default', 'default'), source('b', 'partner')]})
    Config.UPSTREAMS = None
    Config.load()
    assert len(Config.get_upstreams()) == 2
    assert Config.get_upstreams()[1]['name'] == 'partner'


def test_removing_configuration_keeps_data_and_locked_name(system, monkeypatch):
    from intent_hub.app import app
    from intent_hub.api import settings
    monkeypatch.setattr('intent_hub.core.components.get_component_manager', lambda: system)
    pull(system)
    before = system.route_manager.get_all_routes()
    with app.test_request_context(json={'UPSTREAMS': []}):
        assert settings.update_settings()[1] == 200
    assert system.route_manager.get_all_routes() == before
    assert Config.get_upstreams() == []
    with pytest.raises(ValueError, match='不存在'):
        UpstreamAgentService.source_config()
    assert bindings(system.route_manager.repository) == {'default': 'default'}


def test_failed_source_does_not_block_other_queued_source(system, monkeypatch):
    from intent_hub.agent_source import AgentSource
    def fetch(adapter):
        if adapter.base_url == 'https://default.test/api':
            raise RuntimeError('upstream unavailable')
        return [item()]
    monkeypatch.setattr(AgentSource, 'fetch_all', fetch)
    queue = SyncTaskService(system, autostart=False, refresh_diagnostics=False)
    first = queue.enqueue_upstream_pull('default')
    second = queue.enqueue_upstream_pull('b')
    queue.process_next()
    queue.process_next()
    tasks = {t['id']: t for t in queue.list_tasks()}
    assert tasks[first['id']]['error'] == 'upstream unavailable'
    assert tasks[second['id']]['status'] == 'succeeded'
    assert [r.route_key for r in system.route_manager.get_all_routes()] == ['partner.123']


@pytest.mark.parametrize('names', [('a', 'A'), ('a.b', 'c'), ('a b', 'c')])
def test_reject_invalid_or_colliding_names(names):
    with pytest.raises(ValueError):
        validate_upstreams([source('a', names[0]), source('b', names[1])])


def test_legacy_migration_preserves_ids_overrides_and_enqueues_index(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPSTREAMS', None)
    monkeypatch.setattr(Config, 'SOURCE_INSTANCE', 'default')
    path = str(tmp_path / 'legacy.sqlite3')
    manager = RouteManager(path)
    route = RouteConfig(id=42, route_key='old.title', name='Local name', utterances=['local'],
                        source=RouteConfig.RouteSource(type='upstream_agent', source_id='123', source_snapshot={'name': 'Remote'}),
                        sync=RouteConfig.RouteSync(version=3, synced_version=3, manual_overrides=['name']))
    manager.repository.save(route, enqueue=False)
    manager = RouteManager(path)
    migrated = manager.get_route(42)
    assert migrated.route_key == 'default.123'
    assert migrated.name == 'Local name'
    assert migrated.sync.manual_overrides == ['name']
    assert migrated.sync.version == 4 and migrated.sync.synced_version == 3
    assert manager.repository.pending() == [42]
    assert RouteManager(path).get_route(42) == migrated


def test_legacy_conflict_rolls_back_all_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'UPSTREAMS', None)
    path = str(tmp_path / 'conflict.sqlite3')
    manager = RouteManager(path)
    for i in (1, 2):
        manager.repository.save(RouteConfig(id=i, name='Old', route_key=f'old.{i}', utterances=[],
            source=RouteConfig.RouteSource(type='upstream_agent', source_id='same')), enqueue=False)
    before = manager.get_all_routes()
    with pytest.raises(ValueError, match='冲突'):
        RouteManager(path)
    assert manager.repository.all() == before
    assert manager.repository.pending() == []
