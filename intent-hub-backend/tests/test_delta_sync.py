from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.qdrant_wrapper import IntentHubQdrantClient
from intent_hub.route_manager import RouteManager
from intent_hub.services.sync_service import SyncService


@pytest.fixture
def system(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, 'EMBEDDING_MODEL_NAME', 'test-v1')
    q = object.__new__(IntentHubQdrantClient)
    q.collection_name, q.dimensions, q.write_batch_size = 'test', 2, 128
    q.client = QdrantClient(':memory:')
    q.client.create_collection('test', vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    encoder = SimpleNamespace(
        encode=Mock(side_effect=lambda texts: [[1.0, 0.0] for _ in texts]),
        encode_single=Mock(return_value=[1.0, 0.0]),
    )
    rm = RouteManager(str(tmp_path / 'routes.sqlite3'))
    rm.add_route(RouteConfig(id=1, name='one', route_key='one', utterances=['a', 'b'],
                             negative_samples=['no'], sync=RouteConfig.RouteSync(version=1)))
    manager = SimpleNamespace(route_manager=rm, qdrant_client=q, encoder=encoder, ensure_ready=lambda: None)
    service = SyncService(manager)
    service.sync_route(1)
    encoder.encode.reset_mock()
    encoder.encode_single.reset_mock()
    yield manager, service
    q.client.close()


def edit(manager, **changes):
    route = manager.route_manager.get_route(1).model_copy(update=changes)
    route.sync.version += 1
    route.sync.status = 'pending'
    manager.route_manager.update_route(1, route)


def test_unchanged_has_no_embedding_or_remote_writes(system, monkeypatch):
    manager, service = system
    for method in ('upsert', 'delete', 'set_payload'):
        monkeypatch.setattr(manager.qdrant_client.client, method, Mock(side_effect=AssertionError('unexpected write')))
    service.sync_route(1)
    manager.encoder.encode.assert_not_called()
    manager.encoder.encode_single.assert_not_called()


def test_threshold_only_updates_payload(system):
    manager, service = system
    edit(manager, score_threshold=0.8, negative_threshold=0.9)
    service.sync_route(1)
    manager.encoder.encode.assert_not_called()
    manager.encoder.encode_single.assert_not_called()
    points, _ = manager.qdrant_client.client.scroll('test', limit=100)
    for point in points:
        if point.payload.get('is_route_metadata'):
            continue
        key = 'negative_threshold' if point.payload.get('is_negative') else 'score_threshold'
        assert point.payload[key] == (0.9 if key == 'negative_threshold' else 0.8)


def test_one_changed_text_only_encodes_new_text(system):
    manager, service = system
    edit(manager, utterances=['a', 'c'])
    service.sync_route(1)
    assert manager.encoder.encode.call_args_list == [((['c'],), {})]
    manager.encoder.encode_single.assert_not_called()
    points, _ = manager.qdrant_client.client.scroll('test', limit=100)
    assert sorted(p.payload['utterance'] for p in points if 'utterance' in p.payload) == ['a', 'c', 'no']


def test_description_only_and_model_change(system, monkeypatch):
    from intent_hub.intent_description import description_text
    manager, service = system
    edit(manager, description='updated description')
    service.sync_route(1)
    assert manager.encoder.encode.call_args.args[0] == [description_text(manager.route_manager.get_route(1))]
    manager.encoder.encode.reset_mock()
    monkeypatch.setattr(Config, 'EMBEDDING_MODEL_NAME', 'test-v2')
    service.sync_route(1)
    assert set(manager.encoder.encode.call_args.args[0]) == {'a', 'b', 'no', description_text(manager.route_manager.get_route(1))}


def test_delete_sample_does_not_encode(system):
    manager, service = system
    edit(manager, utterances=['a'], negative_samples=[])
    service.sync_route(1)
    manager.encoder.encode.assert_not_called()
    assert manager.qdrant_client.index_summary()['points_count'] == 2


def test_embedding_failure_preserves_old_vectors(system):
    manager, service = system
    edit(manager, utterances=['new'])
    manager.encoder.encode.side_effect = RuntimeError('embedding unavailable')
    with pytest.raises(RuntimeError, match='embedding unavailable'):
        service.sync_route(1)
    points = manager.qdrant_client.get_route_points(1)
    assert {p.payload['utterance'] for p in points if 'utterance' in p.payload} == {'a', 'b', 'no'}
    assert manager.route_manager.get_route(1).sync.status == 'pending'


def test_partial_write_then_revert_is_repaired(system, monkeypatch):
    manager, service = system
    edit(manager, utterances=['a', 'c'])
    original = manager.qdrant_client.delete_points
    monkeypatch.setattr(manager.qdrant_client, 'delete_points', Mock(side_effect=RuntimeError('delete failed')))
    with pytest.raises(RuntimeError, match='delete failed'):
        service.sync_route(1)
    assert manager.qdrant_client.get_route_metadata([1])[1]['sync_schema'] == 0
    assert manager.route_manager.get_route(1).sync.synced_version == 1
    monkeypatch.setattr(manager.qdrant_client, 'delete_points', original)
    edit(manager, utterances=['a', 'b'])
    manager.encoder.encode.reset_mock()
    service.sync_route(1)
    manager.encoder.encode.assert_not_called()
    points = manager.qdrant_client.get_route_points(1)
    assert {p.payload['utterance'] for p in points if 'utterance' in p.payload} == {'a', 'b', 'no'}
    assert manager.qdrant_client.get_route_metadata([1])[1]['sync_schema'] == 1


def test_new_version_during_encoding_is_not_acknowledged(system):
    manager, service = system
    edit(manager, utterances=['c'])
    def encode(texts):
        edit(manager, utterances=['latest'])
        return [[1.0, 0.0] for _ in texts]
    manager.encoder.encode.side_effect = encode
    service.sync_route(1)
    current = manager.route_manager.get_route(1)
    assert current.sync.status == 'pending'
    assert current.sync.synced_version == 1
    manager.encoder.encode.side_effect = lambda texts: [[1.0, 0.0] for _ in texts]
    service.sync_route(1)
    assert manager.route_manager.get_route(1).sync.synced_version == current.sync.version


def test_incremental_noop_uses_manifest_not_sample_scan(system, monkeypatch):
    manager, service = system
    q = manager.qdrant_client
    for method in ('upsert', 'delete', 'set_payload'):
        monkeypatch.setattr(q.client, method, Mock(side_effect=AssertionError('unexpected write')))
    monkeypatch.setattr(q, 'index_summary', Mock(side_effect=AssertionError('unexpected full scan')))
    monkeypatch.setattr(q, 'get_route_points', Mock(side_effect=AssertionError('unexpected sample read')))
    result = service.reindex()
    assert result['skipped_routes'] == 1
    manager.encoder.encode.assert_not_called()


def test_read_failure_does_not_masquerade_as_empty_index(system, monkeypatch):
    manager, service = system
    monkeypatch.setattr(manager.qdrant_client.client, 'scroll', Mock(side_effect=RuntimeError('read failed')))
    with pytest.raises(RuntimeError, match='read failed'):
        service.reindex()
    manager.encoder.encode.assert_not_called()


def test_legacy_missing_metadata_is_upgraded_once(system):
    import uuid
    manager, service = system
    q = manager.qdrant_client
    q.delete_points([str(uuid.uuid5(uuid.NAMESPACE_DNS, 'route-metadata:1'))])
    service.sync_route(1)
    assert len(manager.encoder.encode.call_args.args[0]) == 1  # description only
    manager.encoder.encode.reset_mock()
    service.sync_route(1)
    manager.encoder.encode.assert_not_called()


def test_missing_sample_is_repaired_by_incremental_check(system, monkeypatch):
    manager, service = system
    monkeypatch.setattr('intent_hub.services.diagnostic_service.DiagnosticService.run_async_diagnostics', lambda *a: None)
    q = manager.qdrant_client
    missing = next(p.id for p in q.get_route_points(1) if p.payload.get('utterance') == 'a')
    q.delete_points([missing])
    result = service.reindex()
    assert result['encoded_texts'] == 1
    assert q.index_summary()['points_count'] == 4


def test_eight_routes_noop_needs_only_two_remote_reads(system, monkeypatch):
    manager, service = system
    edit(manager, utterances=[f'one-{n}' for n in range(13)], negative_samples=[])
    service.sync_route(1)
    for rid in range(2, 9):
        manager.route_manager.add_route(RouteConfig(
            id=rid, name=str(rid), route_key=str(rid), utterances=[f'{rid}-{n}' for n in range(11)]))
        service.sync_route(rid)
    manager.encoder.encode.reset_mock()
    client = manager.qdrant_client.client
    calls = {}
    for name in ('scroll', 'count', 'retrieve', 'upsert', 'set_payload', 'delete'):
        calls[name] = Mock(wraps=getattr(client, name))
        monkeypatch.setattr(client, name, calls[name])
    result = service.reindex()
    assert result['skipped_routes'] == 8 and result['encoded_texts'] == 0
    assert {name: call.call_count for name, call in calls.items()} == {
        'scroll': 1, 'count': 1, 'retrieve': 0, 'upsert': 0, 'set_payload': 0, 'delete': 0}
    manager.encoder.encode.assert_not_called()


def test_noop_background_task_has_no_writes_or_diagnostics(system, monkeypatch):
    from intent_hub.services.sync_task_service import SyncTaskService
    manager, _ = system
    queue = SyncTaskService(manager, autostart=False)
    task = queue.enqueue_routes([1])
    for method in ('upsert', 'delete', 'set_payload'):
        monkeypatch.setattr(manager.qdrant_client.client, method, Mock(side_effect=AssertionError('unexpected write')))
    refresh = Mock(side_effect=AssertionError('unexpected diagnostics'))
    monkeypatch.setattr(queue, '_refresh_diagnostics_if_idle', refresh)
    assert queue.process_next()
    result = next(t for t in queue.list_tasks() if t['id'] == task['id'])
    assert result['status'] == 'succeeded'
    assert result['result']['routes']['1']['encoded_texts'] == 0
    assert result['queue_wait_ms'] >= 0 and result['execution_ms'] >= result['lock_wait_ms'] >= 0
    refresh.assert_not_called()


def test_changed_task_followed_by_noop_still_refreshes_diagnostics(system, monkeypatch):
    from intent_hub.services.sync_task_service import SyncTaskService
    manager, _ = system
    edit(manager, score_threshold=0.8)
    queue = SyncTaskService(manager, autostart=False)
    queue.enqueue_routes([1])
    refresh = Mock()
    monkeypatch.setattr('intent_hub.services.diagnostic_service.DiagnosticService.run_async_diagnostics', refresh)
    # Queue a following scan while the route task is already running.
    real_sync = SyncService.sync_route
    def sync_with_followup(service, rid):
        queue.enqueue_incremental_reindex()
        return real_sync(service, rid)
    monkeypatch.setattr(SyncService, 'sync_route', sync_with_followup)
    assert queue.process_next()
    refresh.assert_not_called()
    assert queue.process_next()
    refresh.assert_called_once_with('full')


def test_description_change_does_not_patch_sample_points(system, monkeypatch):
    manager, service = system
    q = manager.qdrant_client
    before = {p.id: p.payload for p in q.get_route_points(1) if not p.payload.get('is_route_metadata')}
    patch = Mock(wraps=q.patch_points)
    monkeypatch.setattr(q, 'patch_points', patch)
    edit(manager, description='only description changed')
    service.sync_route(1)
    after = {p.id: p.payload for p in q.get_route_points(1) if not p.payload.get('is_route_metadata')}
    assert before == after
    assert not any(set(call.args[0]) & set(before) for call in patch.call_args_list)


def test_source_baseline_and_details_changes_do_not_touch_index(system, monkeypatch):
    manager, service = system
    route = manager.route_manager.get_route(1)
    route.source = RouteConfig.RouteSource(type='upstream_agent', source_id='one', source_snapshot={'description': 'new baseline'})
    route.details = {'text': 'new upstream description'}
    manager.route_manager.repository.save(route, enqueue=False)
    for method in ('upsert', 'delete', 'set_payload'):
        monkeypatch.setattr(manager.qdrant_client.client, method, Mock(side_effect=AssertionError('unexpected write')))
    assert service.sync_route(1)['changed'] is False
    manager.encoder.encode.assert_not_called()


def test_metadata_hash_wins_over_legacy_sample_hashes(system):
    manager, service = system
    q = manager.qdrant_client
    samples = [p.id for p in q.get_route_points(1) if not p.payload.get('is_route_metadata')]
    q.patch_points(samples, {'route_hash': 'legacy-stale-hash'})
    edit(manager, description='updated')
    service.sync_route(1)
    expected = manager.route_manager.compute_route_hash(manager.route_manager.get_route(1))
    assert q.index_summary()['route_hashes'] == {1: expected}
