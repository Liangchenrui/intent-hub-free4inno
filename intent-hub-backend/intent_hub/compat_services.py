"""BUPT serializers/adapters over the single set of domain services."""
import time

from intent_hub.config import Config
from intent_hub.models import PredictRequest, RouteConfig
from intent_hub.services.route_service import RouteService
from intent_hub.services.prediction_service import PredictionService as CorePrediction
from intent_hub.services.sync_task_service import get_sync_task_service
from intent_hub.services.sync_service import SyncService as CoreSync
from intent_hub.services.diagnostic_service import DiagnosticService as CoreDiagnostic
from intent_hub.services.collection_service import CollectionService as CoreCollection
from intent_hub.services.qdrant_import_service import QdrantImportService
from intent_hub.services.upstream_agent_service import UpstreamAgentService


class PredictionService:
    def __init__(self, components):
        self.components = components

    def route(self, query):
        components = self.components
        if hasattr(components, 'ready_snapshot'):
            components = components.ready_snapshot()
        results = CorePrediction(components).predict(PredictRequest(text=query))
        matched = [r for r in results if r.match_source != 'default']
        return {'matched': bool(matched), 'agents': [
            {'agent': components.route_manager.get_route(r.id).details, 'score': r.score}
            for r in matched], 'text': None if matched else Config.DEFAULT_ROUTE_TEXT,
            'match_source': results[0].match_source, 'fallback_status': results[0].fallback_status}


class PullService:
    def __init__(self, components):
        self.components = components

    def pull(self):
        from intent_hub.agent_source import AgentSource
        result = UpstreamAgentService(self.components, source=AgentSource(label_ids=Config.AGENT_API_LABEL_IDS or "87,88,89"), default_threshold=0.8).pull()
        store = self.components.agent_store
        if result.get('last_pulled_at'):
            store.set_metadata('last_pull_at', result['last_pulled_at'])
        return {**{k: v for k, v in result.items() if k not in {'routes_count', 'affected_route_ids', 'last_pulled_at'}},
                'disabled': result['upstream_missing'], 'upstream_changed': result['updated'],
                'agents_count': result['routes_count'], 'last_pull_at': store.get_metadata('last_pull_at')}


class SyncService:
    def __init__(self, components):
        self.components = components

    def sync(self, mode='incremental', agent_ids=None):
        if mode not in {'incremental', 'full'}:
            raise ValueError('mode 仅支持 incremental 或 full')
        if agent_ids is not None and (not isinstance(agent_ids, list) or any(type(i) is not int for i in agent_ids)):
            raise ValueError('agent_ids 必须为整数数组')
        queue = get_sync_task_service(self.components)
        ids = [self.components.agent_store.internal_id(i) for i in agent_ids] if agent_ids is not None else None
        if mode == 'full' and ids is not None:
            raise ValueError('full 不支持局部 agent_ids；请使用 incremental')
        if not self.components.agent_store.active() and ids is None:
            return {'mode': mode, 'agents_count': 0, 'indexed_agents_count': 0, 'changed_agents': 0,
                    'deleted_agents': 0, 'unchanged_agents': 0, 'positive_points': 0, 'negative_points': 0,
                    'warning': '本地没有可同步的 Agent，已保留现有索引'}
        task = queue.enqueue_routes(ids) if ids is not None else queue.enqueue_reindex(mode == 'full')
        deadline = time.monotonic() + Config.SYNC_WAIT_SECONDS
        while time.monotonic() < deadline:
            current = next(t for t in queue.list_tasks() if t['id'] == task['id'])
            if current['status'] == 'succeeded':
                active = self.components.agent_store.active()
                if agent_ids is not None:
                    active = [a for a in active if a.id in agent_ids]
                core = current.get('result') or {}
                changed = core.get('updated_routes', core.get('success_count', len(active)))
                self.components.agent_store.set_metadata('last_vector_sync_at', current['updated_at'])
                return {'mode': mode, 'agents_count': len(active), 'indexed_agents_count': len(active),
                        'changed_agents': changed, 'deleted_agents': core.get('deleted_routes', 0),
                        'unchanged_agents': max(0, len(active) - changed),
                        'positive_points': sum(len(a.utterances) for a in active),
                        'negative_points': sum(len(a.negative_samples) for a in active),
                        'description_points': len(active), **({'collection': Config.QDRANT_COLLECTION} if mode == 'full' else {})}
            if current['status'] in {'error', 'superseded'}:
                raise RuntimeError(f"Sync task {task['id']} {current['status']}")
            time.sleep(0.05)
        raise TimeoutError(f"Sync task {task['id']} is still pending; query /sync-tasks")

    def status(self):
        routes = [r for r in self.components.route_manager.get_all_routes() if r.lifecycle_status == 'active']
        actual = self.components.qdrant_client.index_summary()
        expected = sum(len(r.utterances) + len(r.negative_samples) + 1 for r in routes)
        hashes = {r.id: self.components.route_manager.compute_route_hash(r) for r in routes}
        return {'agents_count': len(self.components.agent_store.all()), 'active_agents_count': len(routes),
                'pending_changes': sum(actual['route_hashes'].get(k) != v for k, v in hashes.items()) + len(set(actual['route_ids']) - set(hashes)),
                'collection': Config.QDRANT_COLLECTION, 'expected_points': expected, 'points_count': actual['points_count'],
                'synced': actual['points_count'] == expected and actual['route_hashes'] == hashes,
                'last_pull_at': self.components.agent_store.get_metadata('last_pull_at'),
                'last_vector_sync_at': self.components.agent_store.get_metadata('last_vector_sync_at')}


class DiagnosticService:
    def __init__(self, components):
        self.components = components
        self.core = CoreDiagnostic(components)

    def _external(self, entity_id):
        return self.components.agent_store.repo.legacy_id('bupt', Config.SOURCE_INSTANCE, entity_id)

    def _map(self, result):
        result = result.model_copy(deep=True)
        result.route_id = self._external(result.route_id)
        for overlap in result.overlaps:
            overlap.target_route_id = self._external(overlap.target_route_id)
        return result

    def analyze_all(self, refresh=False, max_conflicts=10):
        return [self._map(r) for r in self.core.analyze_all_overlaps(use_cache=not refresh, max_conflicts_per_pair=max_conflicts)]

    def analyze_route(self, agent_id):
        return self._map(self.core.analyze_route_overlap(self.components.agent_store.internal_id(agent_id)))

    def umap_points(self, **kwargs):
        result = self.core.build_umap_projection(**kwargs)
        for point in result['points']:
            point['route_id'] = self._external(point['route_id'])
        return result

    def repair(self, source_id, target_id):
        result = self.core.get_repair_suggestions(self.components.agent_store.internal_id(source_id), self.components.agent_store.internal_id(target_id))
        data = result.model_dump()
        data['route_id'] = self._external(result.route_id)
        return data

    def merge(self, source_id, target_id, title, text=''):
        return self.components.agent_store.merge(source_id, target_id, title, text)


class CollectionService:
    def __init__(self, components):
        self.components = components
        self.core = CoreCollection(components)

    def list_collections(self):
        data = self.core.list_collections()
        return {k: data[k] for k in ('current', 'collections')}

    def create_collection(self, name):
        return self.core.create_collection(name)

    def restore_collection(self, name):
        name = self.core.normalize_name(name)
        service = QdrantImportService(self.components.route_manager)
        points = service._scroll_payloads(name)
        routes = service._build_routes(points, name)
        if not routes:
            raise ValueError('Collection 中没有可恢复的实体')
        with CoreSync.execution_lock:
            store = self.components.agent_store
            metadata_ids = {(p.get('payload') or {}).get('route_config', {}).get('id')
                            for p in points if (p.get('payload') or {}).get('is_route_metadata')}
            with store.repo.transaction() as db:
                existing = {r.route_key: r for r in store.manager.get_all_routes()}
                for route in routes:
                    legacy_id = route.id
                    # Unified metadata has stable keys; legacy BUPT payload IDs are aliases.
                    current = existing.get(route.route_key) if legacy_id in metadata_ids else (
                        store.manager.get_route(store.internal_id(legacy_id)) if store.get(legacy_id) else None)
                    if current:
                        if legacy_id not in metadata_ids:
                            route = current.model_copy(update={
                                'name': route.name, 'utterances': route.utterances,
                                'negative_samples': route.negative_samples,
                                'score_threshold': route.score_threshold,
                                'negative_threshold': route.negative_threshold,
                                'lifecycle_status': 'active'}, deep=True)
                        route.id, route.route_key = current.id, current.route_key
                    else:
                        route.id = store.repo.allocate(db)
                        if legacy_id not in metadata_ids:
                            route.route_key = f'bupt.{Config.SOURCE_INSTANCE}.{legacy_id}'
                            route.details = {'restored_from_collection': name}
                    RouteService._mark_changed(route, current)
                    store.repo.save(route, db)
                    if legacy_id not in metadata_ids:
                        store.repo.bind('bupt', Config.SOURCE_INSTANCE, legacy_id, route.id, db)
                Config.save({'QDRANT_COLLECTION': name})
            self.components.reset_components()
        return {'collection': name, 'restored_agents': len(routes), 'positive_texts': sum(len(r.utterances) for r in routes),
                'negative_texts': sum(len(r.negative_samples) for r in routes), 'points_count': len(points),
                'skipped_points': sum(bool((p.get('payload') or {}).get('is_route_metadata')) for p in points)}
