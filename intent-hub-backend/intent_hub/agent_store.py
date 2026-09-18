"""BUPT model adapter. All data lives in the shared route repository."""
from datetime import datetime, timezone

from intent_hub.compat_models import Agent
from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.services.route_service import RouteService
from intent_hub.services.upstream_agent_service import UpstreamAgentService

FIELDS = {'title': 'name', 'text': 'description'}


class AgentStore:
    def __init__(self, components):
        self.components = components
        self.manager = components.route_manager
        self.repo = self.manager.repository
        # Materialize unambiguous external IDs for entities from either source.
        with self.repo.transaction() as db:
            aliases = list(db.execute("SELECT legacy_id, entity_id FROM identity WHERE contract='bupt' AND source=?", (Config.SOURCE_INSTANCE,)))
            used = {r[0] for r in aliases}
            mapped = {r[1] for r in aliases}
            next_negative = min(used | {0}) - 1
            for (entity_id,) in db.execute('SELECT id FROM entities ORDER BY id').fetchall():
                if entity_id not in mapped:
                    legacy = entity_id if entity_id not in used else next_negative
                    if legacy == next_negative:
                        next_negative -= 1
                    self.repo.bind('bupt', Config.SOURCE_INSTANCE, legacy, entity_id, db)
                    used.add(legacy)

    def internal_id(self, agent_id):
        mapped = self.repo.resolve('bupt', Config.SOURCE_INSTANCE, agent_id)
        if mapped is not None:
            return mapped
        # Unmapped entities are exposed by internal ID, unless that ID is already an alias.
        route = self.manager.get_route(agent_id)
        if route and self.repo.legacy_id('bupt', Config.SOURCE_INSTANCE, route.id) == agent_id:
            return agent_id
        raise ValueError('Agent 不存在')

    def from_route(self, route):
        source = route.source
        upstream = bool(source and source.type == 'upstream_agent')
        reverse = {v: k for k, v in FIELDS.items()}
        return Agent(
            id=self.repo.legacy_id('bupt', Config.SOURCE_INSTANCE, route.id),
            title=route.name, text=route.description, utterances=route.utterances,
            negative_samples=route.negative_samples, score_threshold=route.score_threshold,
            negative_threshold=route.negative_threshold, details=route.details,
            updated_at=route.updated_at,
            source_type='upstream' if upstream else 'local',
            upstream_id=int(source.source_id) if upstream and source.source_id and source.source_id.lstrip('-').isdigit() else None,
            upstream_present=source.upstream_present if source else None,
            source_snapshot={reverse.get(k, k): v for k, v in (source.source_snapshot if source else {}).items()},
            manual_overrides=[reverse.get(k, k) for k in (route.sync.manual_overrides if route.sync else [])],
            lifecycle_status=route.lifecycle_status if route.lifecycle_status in {'active', 'deleted'} else 'inactive',
        )

    def all(self):
        return [self.from_route(r) for r in self.manager.get_all_routes()]

    def active(self):
        return [a for a in self.all() if a.lifecycle_status == 'active']

    def get(self, agent_id):
        try:
            route = self.manager.get_route(self.internal_id(agent_id))
        except ValueError:
            return None
        return self.from_route(route) if route else None

    def create_local(self, **values):
        with self.repo.transaction() as db:
            entity_id = self.repo.allocate(db)
            minimum = db.execute("SELECT MIN(legacy_id) FROM identity WHERE contract='bupt' AND source=?", (Config.SOURCE_INSTANCE,)).fetchone()[0]
            legacy_id = min(minimum or 0, 0) - 1
            mapped = {FIELDS.get(k, k): v for k, v in values.items()}
            route = RouteConfig(id=entity_id, route_key=f'local.agent.{entity_id}',
                source=RouteConfig.RouteSource(type='web_manual'),
                sync=RouteConfig.RouteSync(status='pending', version=1), **mapped)
            self.repo.save(route, db)
            self.repo.bind('bupt', Config.SOURCE_INSTANCE, legacy_id, entity_id, db)
        return self.from_route(route)

    def update(self, agent_id, values):
        entity_id = self.internal_id(agent_id)
        route = self.manager.get_route(entity_id)
        mapped = {FIELDS.get(k, k): v for k, v in values.items()}
        if mapped.get('lifecycle_status') == 'inactive':
            mapped['lifecycle_status'] = 'disabled'
        updated = RouteConfig.model_validate({**route.model_dump(), **mapped})
        updated = RouteService(self.components).update_route(entity_id, updated)
        overrides = sorted(set(updated.sync.manual_overrides) | set(mapped))
        updated = self.manager.update_sync_state(entity_id, manual_overrides=overrides)
        return self.from_route(updated)

    def restore_fields(self, agent_id, fields):
        route = UpstreamAgentService(self.components).restore_fields(self.internal_id(agent_id), [FIELDS.get(k, k) for k in fields])
        return self.from_route(route)

    def get_metadata(self, key):
        return self.repo.metadata(key)

    def set_metadata(self, key, value):
        self.repo.metadata(key, value)

    def merge(self, source_id, target_id, title, text):
        source = self.internal_id(source_id)
        target = self.internal_id(target_id)
        if source == target:
            raise ValueError('Cannot merge an Agent into itself')
        with self.repo.transaction() as db:
            rows = [db.execute('SELECT body FROM entities WHERE id=?', (key,)).fetchone() for key in (source, target)]
            if not all(rows):
                raise ValueError('Agent 不存在')
            left, right = [RouteConfig.model_validate_json(row[0]) for row in rows]
            entity_id = self.repo.allocate(db)
            route = RouteConfig(id=entity_id, name=title, description=text,
                route_key=f'local.agent.{entity_id}', source=RouteConfig.RouteSource(type='web_manual'),
                utterances=list(dict.fromkeys(left.utterances + right.utterances)),
                negative_samples=list(dict.fromkeys(left.negative_samples + right.negative_samples)),
                score_threshold=max(left.score_threshold, right.score_threshold),
                negative_threshold=max(left.negative_threshold, right.negative_threshold),
                sync=RouteConfig.RouteSync(status='pending', version=1))
            self.repo.save(route, db)
            minimum = db.execute("SELECT MIN(legacy_id) FROM identity WHERE contract='bupt' AND source=?", (Config.SOURCE_INSTANCE,)).fetchone()[0]
            self.repo.bind('bupt', Config.SOURCE_INSTANCE, min(minimum or 0, 0) - 1, entity_id, db)
            for old in (left, right):
                previous = old.model_copy(deep=True)
                old.lifecycle_status = 'disabled'
                RouteService._mark_changed(old, previous, manual_overrides=sorted(
                    set(previous.sync.manual_overrides if previous.sync else []) | {"lifecycle_status"}))
                self.repo.save(old, db)
            db.execute('INSERT INTO metadata VALUES (?,?)', (f'merge:{entity_id}', f'{source},{target}'))
        return self.from_route(route)
