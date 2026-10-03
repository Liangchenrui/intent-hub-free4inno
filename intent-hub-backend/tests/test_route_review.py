"""Review alerts reflect upstream changes, independent of routing/index state."""
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from intent_hub.agent_source import AgentSource
from intent_hub.app import app
from intent_hub.config import Config
from intent_hub.models import RouteConfig, RouteReview
from intent_hub.route_manager import RouteManager
from intent_hub.services.delta_sync import business_snapshot
from intent_hub.services.import_service import ImportService
from intent_hub.services.route_service import RouteService
from intent_hub.services.upstream_agent_service import UpstreamAgentService


@pytest.fixture
def review_system(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'AUTH_ENABLED', False)
    manager = RouteManager(str(tmp_path / 'review.sqlite3'))
    components = SimpleNamespace(route_manager=manager)
    monkeypatch.setattr('intent_hub.api.routes.get_component_manager', lambda: components)
    item = dict(source_id='42', name='Agent', description='original',
                utterances=['remote'], negative_samples=['negative'], details={'parameters': []})
    service = UpstreamAgentService(components, source=SimpleNamespace(fetch_all=lambda: [item]))
    service.pull()
    manager.update_sync_state(1, status='synced', synced_version=1)
    with manager.repository.transaction() as db:
        db.execute('DELETE FROM outbox')
    return manager, components, service, item


def acknowledge(manager, needs_review=False, version=None):
    version = manager.get_route(1).review.version if version is None else version
    return app.test_client().patch('/compat/master/routes/1/review', json={
        'needs_review': needs_review, 'expected_version': version})


def test_create_acknowledge_reopen_and_noop_do_not_index(review_system):
    manager, _, service, _ = review_system
    before = manager.get_route(1)
    assert before.review.needs_review and before.review.reason == 'created'
    assert before.utterances == before.negative_samples == []
    assert acknowledge(manager).status_code == 200
    cleared = manager.get_route(1)
    assert not cleared.review.needs_review
    assert cleared.sync == before.sync and cleared.updated_at == before.updated_at
    assert business_snapshot(cleared) == business_snapshot(before)
    assert manager.compute_route_hash(cleared) == manager.compute_route_hash(before)
    assert service.pull()['unchanged'] == 1
    assert manager.get_route(1) == cleared
    assert acknowledge(manager).get_json()['review']['version'] == cleared.review.version
    assert acknowledge(manager, True).status_code == 200
    assert manager.get_route(1).review.reason == 'manual'
    assert manager.repository.pending() == []


def test_overridden_update_and_detail_changes_realert_and_accumulate(review_system):
    manager, _, service, item = review_system
    acknowledge(manager)
    route = manager.get_route(1)
    route.description = 'local'
    route.sync.manual_overrides = ['description']
    route.utterances = ['manual', 'learned']
    route.fallback_utterances = {'learned': '2026-09-30T00:00:00Z'}
    manager.repository.save(route, enqueue=False)
    item['description'] = 'remote changed'
    result = service.pull()
    current = manager.get_route(1)
    assert current.description == 'local' and current.utterances == ['manual', 'learned']
    assert current.fallback_utterances == route.fallback_utterances
    assert current.review.needs_review and current.review.changed_fields == ['description']
    assert result['effective_updated'] == 0 and manager.repository.pending() == []
    item['details']['parameters'] = [{'name': 'city'}]
    service.pull()
    assert manager.get_route(1).review.changed_fields == ['description', 'details.parameters']
    assert manager.repository.pending() == []


def test_stale_acknowledgement_and_simultaneous_admins(review_system):
    manager, _, service, item = review_system
    version = manager.get_route(1).review.version
    item['name'] = 'Renamed'
    service.pull()
    assert acknowledge(manager, version=version).status_code == 409
    assert manager.get_route(1).review.needs_review
    version = manager.get_route(1).review.version
    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: acknowledge(manager, version=version).status_code, range(2)))
    assert sorted(statuses) == [200, 409]


def test_generic_edits_import_and_index_restore_preserve_latest_review(review_system):
    manager, components, service, item = review_system
    acknowledge(manager)
    stale = manager.get_route(1).model_copy(deep=True)
    item['description'] = 'new capability'
    service.pull()
    newest = manager.get_route(1).review.model_copy(deep=True)
    stale.utterances = ['local edit']
    RouteService(components).update_route(1, stale)
    assert manager.get_route(1).review == newest
    imported = manager.get_route(1).model_copy(deep=True)
    imported.review = RouteReview()
    ImportService(components).import_routes([imported])
    assert manager.get_route(1).review == newest
    recovered = manager.get_route(1).model_copy(deep=True)
    recovered.review = RouteReview()
    manager.replace_routes([recovered])
    assert manager.get_route(1).review == newest


def test_legacy_records_default_reviewed_and_corpus_changes_do_not_alert(review_system):
    manager, _, service, item = review_system
    with manager.repository.transaction() as db:
        db.execute("UPDATE entities SET body=json_remove(body, '$.review') WHERE id=1")
    assert not manager.get_route(1).review.needs_review
    item['utterances'] = ['different']
    item['negative_samples'] = ['different negative']
    item['details'].update(extent00='malformed', extent01=None)
    assert service.pull()['unchanged'] == 1
    assert not manager.get_route(1).review.needs_review
    item['details']['viewCount'] = 20
    service.pull()
    assert not manager.get_route(1).review.needs_review
    assert manager.repository.pending() == []


@pytest.mark.parametrize('field', ['utterances', 'negative_samples'])
def test_corpus_restore_rejected_without_mutation(review_system, field):
    manager, _, service, _ = review_system
    before = manager.get_route(1)
    with pytest.raises(ValueError, match='本地维护'):
        service.restore_fields(1, ['name', field])
    assert manager.get_route(1) == before


@pytest.mark.parametrize('payload', [None, [], {}, {'needs_review': 'false', 'expected_version': 1},
    {'needs_review': False, 'expected_version': True}, {'needs_review': False, 'expected_version': -1},
    {'needs_review': False, 'expected_version': 1, 'extra': True}])
def test_review_request_validation(review_system, payload):
    manager, _, _, _ = review_system
    before = manager.get_route(1)
    response = app.test_client().patch('/routes/1/review', json=payload)
    assert response.status_code == 400
    assert manager.get_route(1) == before


def test_review_auth_and_missing_route(review_system, monkeypatch):
    assert app.test_client().patch('/routes/999/review', json={
        'needs_review': False, 'expected_version': 0}).status_code == 404
    monkeypatch.setattr(Config, 'AUTH_ENABLED', True)
    assert acknowledge(review_system[0]).status_code == 401


@pytest.mark.parametrize('corpora', [{}, {'extent00': 'invalid', 'extent01': {'bad': True}}])
def test_upstream_missing_or_invalid_corpora_are_ignored(corpora):
    details = {'id': 1, 'title': 'Agent', 'text': 'Description', **corpora}
    class Session:
        def get(self, url, **kwargs):
            data = {'records': [{'resource': {'id': 1}}]} if url.endswith('/search') else details
            return SimpleNamespace(raise_for_status=lambda: None, json=lambda: {'code': 200, 'data': data})
    source = AgentSource(Session(), base_url='https://example.test/api', label_ids='1')
    rows = source.fetch_all()
    assert not source.failed_ids and len(rows) == 1
    assert rows[0]['utterances'] == rows[0]['negative_samples'] == []
    assert rows[0]['details'] == details
