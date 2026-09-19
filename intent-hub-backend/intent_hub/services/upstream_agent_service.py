"""Merge upstream Agents into the master route model without writing vectors."""

from datetime import datetime, timezone
import json
import threading
from time import perf_counter

from intent_hub.agent_source import AgentSource
from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_compare import COMPARABLE_FIELDS, snapshots_equal, fields_equal
from intent_hub.services.route_service import RouteService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpstreamAgentService:
    def __init__(self, component_manager, source=None, default_threshold=0.75):
        self.components = component_manager
        self.source = source or AgentSource()
        self.default_threshold = default_threshold

    _pull_lock = threading.Lock()

    def pull(self, progress=None, expected_source=None) -> dict:
        # Serialize compatibility and background pulls; do not hold a DB lock over HTTP.
        with self._pull_lock:
            started = perf_counter()
            source_instance = Config.SOURCE_INSTANCE
            expected_source = expected_source or self.source_config()
            scope = {
                'url': getattr(self.source, 'base_url', None) or Config.AGENT_API_URL,
                'labels': sorted(set(str(getattr(self.source, 'label_ids', None) or Config.AGENT_API_LABEL_IDS or '').split(','))),
            }
            incoming = self.source.fetch_all()
            fetched = perf_counter()
            if progress:
                progress("comparing")
            if expected_source is not None and expected_source != self.source_config():
                raise ValueError("上游配置已变更，请重新拉取")
            repo = self.components.route_manager.repository
            with repo.transaction() as db:
                current = [RouteConfig.model_validate_json(row[0]) for row in
                           db.execute("SELECT body FROM entities ORDER BY id")]
                previous = db.execute('SELECT value FROM metadata WHERE key=?',
                                      (f'upstream_pull:{source_instance}',)).fetchone()
                previous = json.loads(previous[0]) if previous else None
                candidates = None if previous is None else (
                    set(previous.get('listed_source_ids', [])) if previous.get('scope') == scope else set())
                result = self._merge(incoming, current, repo, db, source_instance, candidates)
                result["timings_ms"] = {
                    "fetch": round((fetched - started) * 1000, 3),
                    "compare_save": round((perf_counter() - fetched) * 1000, 3),
                }
                result['upstream_requests'] = getattr(self.source, 'request_count', 0)
                result['detail_requests'] = getattr(self.source, 'detail_request_count', 0)
                # Preserve last complete membership across incomplete/empty fetches.
                membership = sorted(set(getattr(self.source, 'listed_ids', set())) | {i['source_id'] for i in incoming})
                if not incoming or not getattr(self.source, 'complete', True):
                    membership = sorted(set(membership) | set(candidates or []))
                db.execute("INSERT INTO metadata VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (f"upstream_pull:{source_instance}", json.dumps({**result, 'scope': scope, 'listed_source_ids': membership})))
            return result

    @staticmethod
    def source_config():
        return {key: getattr(Config, key) for key in
                ("SOURCE_INSTANCE", "AGENT_API_URL", "AGENT_API_LABEL_IDS")}

    def _merge(self, incoming, current_routes, repo, db, source_instance, missing_candidates=None):
        pulled_at = now_iso()
        result = dict(created=0, updated=0, effective_updated=0, baseline_updated=0,
                      unchanged=0, preserved_overrides=0, upstream_missing=0,
                      failed=len(getattr(self.source, "failed_ids", [])),
                      failed_source_ids=getattr(self.source, "failed_ids", []),
                      routes_count=len(current_routes), affected_route_ids=[], last_pulled_at=pulled_at)
        if not incoming:
            result["warning"] = "上游未返回可用 Agent，本地数据保持不变"
            return result
        source_routes = [r for r in current_routes
                         if r.source and r.source.type == "upstream_agent"
                         and r.source.instance == source_instance and r.source.source_id]
        failed_ids = set(getattr(self.source, "failed_ids", []))
        by_key = {r.route_key: r for r in current_routes}
        incoming_keys = {}
        for item in incoming:
            key = self.components.route_manager.normalize_route_key(item.get('route_key') or item['name'])
            if not key:
                raise ValueError('上游 Agent 缺少有效路由标识')
            if key in incoming_keys:
                raise ValueError(f'上游路由标识重复：{key}；本次拉取未保存')
            incoming_keys[key] = item
        matched_ids = set()
        for route_key, item in incoming_keys.items():
            snapshot = {field: item[field] for field in COMPARABLE_FIELDS}
            current = by_key.get(route_key)
            if current is None:
                route_id = repo.allocate(db)
                route = RouteConfig(
                    id=route_id, route_key=route_key, details=item.get("details", {}),
                    score_threshold=self.default_threshold,
                    **snapshot,
                    source=RouteConfig.RouteSource(
                        type="upstream_agent", instance=source_instance, source_id=item["source_id"],
                        import_origin="agent_api", managed_fields=list(COMPARABLE_FIELDS),
                        source_snapshot=snapshot, upstream_present=True),
                    sync=RouteConfig.RouteSync(status="pending", version=1))
                repo.save(route, db)
                result["created"] += 1
                result["affected_route_ids"].append(route.id)
                continue
            matched_ids.add(current.id)
            route = current.model_copy(deep=True)
            if route.source is None or route.source.type != 'upstream_agent':
                route.source = RouteConfig.RouteSource(type='upstream_agent', instance=source_instance,
                    source_id=item['source_id'], import_origin='agent_api',
                    managed_fields=list(COMPARABLE_FIELDS), source_snapshot={}, upstream_present=True)
            route.source.instance = source_instance
            route.source.source_id = item['source_id']
            overrides = set(route.sync.manual_overrides if route.sync else [])
            result["preserved_overrides"] += len(overrides & set(COMPARABLE_FIELDS))
            source_changed = not snapshots_equal(route.source.source_snapshot or {}, snapshot)
            if source_changed:
                route.source.source_snapshot = snapshot
            for field, value in snapshot.items():
                if field not in overrides and not fields_equal(field, getattr(route, field), value):
                    setattr(route, field, value)
            details = item.get("details", route.details)
            # Raw corpus ordering/formatting is not a business mutation either.
            managed_keys = {'title', 'text', 'extent00', 'extent01'}
            details_changed = ({k: v for k, v in details.items() if k not in managed_keys}
                               != {k: v for k, v in route.details.items() if k not in managed_keys})
            if source_changed or details_changed:
                route.details = details
            route.source.upstream_present = True
            if route.lifecycle_status == "disabled" and "lifecycle_status" not in overrides:
                route.lifecycle_status = "active"
            effective_changed = self.components.route_manager.compute_route_hash(current) != self.components.route_manager.compute_route_hash(route)
            if effective_changed:
                RouteService._mark_changed(route, previous=current)
                result["affected_route_ids"].append(route.id)
                result["effective_updated"] += 1
            changed = route != current
            if changed:
                repo.save(route, db, enqueue=effective_changed)
                if not effective_changed:
                    result["baseline_updated"] += 1
            else:
                result["unchanged"] += 1
            result["updated"] += int(source_changed)
        if getattr(self.source, "complete", True):
            for current in source_routes:
                source_id = current.source.source_id
                if missing_candidates is not None and source_id not in missing_candidates:
                    continue
                if current.id in matched_ids or source_id in failed_ids or current.source.upstream_present is False:
                    continue
                route = current.model_copy(deep=True)
                route.source.upstream_present = False
                route.lifecycle_status = "disabled"
                RouteService._mark_changed(route, previous=current)
                repo.save(route, db)
                result["affected_route_ids"].append(route.id)
                result["upstream_missing"] += 1
        else:
            result["warning"] = "上游列表不完整，已更新可用条目，未判定缺失 Agent"
        result["routes_count"] += result["created"]
        return result

    def restore_fields(self, route_id: int, fields: list[str]) -> RouteConfig:
        manager = self.components.route_manager
        current = manager.get_route(route_id)
        if not current or not current.source or current.source.type != "upstream_agent":
            raise ValueError("只能恢复上游 Agent 字段")
        allowed = set(fields) & set(COMPARABLE_FIELDS)
        if not allowed:
            raise ValueError("没有可恢复的字段")
        route = current.model_copy(deep=True)
        for field in allowed:
            if field in route.source.source_snapshot:
                setattr(route, field, route.source.source_snapshot[field])
        route.sync = route.sync or RouteConfig.RouteSync()
        route.sync.manual_overrides = sorted(set(route.sync.manual_overrides) - allowed)
        RouteService._mark_changed(
            route,
            previous=current,
            manual_overrides=route.sync.manual_overrides,
        )
        manager.update_route(route_id, route)
        return route
