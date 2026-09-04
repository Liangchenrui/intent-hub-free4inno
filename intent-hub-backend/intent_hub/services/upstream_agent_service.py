"""Merge upstream Agents into the master route model without writing vectors."""

from datetime import datetime, timezone

from intent_hub.agent_source import AgentSource
from intent_hub.models import RouteConfig
from intent_hub.route_compare import COMPARABLE_FIELDS, snapshots_equal
from intent_hub.services.route_service import RouteService


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UpstreamAgentService:
    def __init__(self, component_manager, source=None):
        self.components = component_manager
        self.source = source or AgentSource()

    def pull(self) -> dict:
        incoming = self.source.fetch_all()
        current_routes = self.components.route_manager.get_all_routes()
        if not incoming:
            return {
                "created": 0,
                "updated": 0,
                "unchanged": 0,
                "preserved_overrides": 0,
                "upstream_missing": 0,
                "routes_count": len(current_routes),
                "warning": "上游未返回 Agent，本地数据保持不变",
            }

        pulled_at = now_iso()
        by_source_id = {
            route.source.source_id: route
            for route in current_routes
            if route.source and route.source.type == "upstream_agent" and route.source.source_id
        }
        incoming_ids = {item["source_id"] for item in incoming}
        routes_by_id = {route.id: route for route in current_routes}
        used_keys = {route.route_key for route in current_routes}
        created = updated = unchanged = preserved = missing = 0
        affected_ids: list[int] = []

        for item in incoming:
            snapshot = {field: item[field] for field in COMPARABLE_FIELDS}
            current = by_source_id.get(item["source_id"])
            if current is None:
                route_id = self.components.route_manager.allocate_route_id()
                route_key = self._unique_route_key(item["name"], route_id, used_keys)
                used_keys.add(route_key)
                route = RouteConfig(
                    id=route_id,
                    name=item["name"] or f"Agent {item['source_id']}",
                    route_key=route_key,
                    description=item["description"],
                    utterances=item["utterances"],
                    negative_samples=item["negative_samples"],
                    source=RouteConfig.RouteSource(
                        type="upstream_agent",
                        source_id=item["source_id"],
                        import_origin="agent_api",
                        managed_fields=list(COMPARABLE_FIELDS),
                        source_snapshot=snapshot,
                        upstream_present=True,
                        last_pulled_at=pulled_at,
                    ),
                    sync=RouteConfig.RouteSync(status="pending", version=1),
                )
                routes_by_id[route.id] = route
                created += 1
                affected_ids.append(route.id)
                continue

            route = current.model_copy(deep=True)
            previous_snapshot = route.source.source_snapshot or {}
            source_changed = not snapshots_equal(previous_snapshot, snapshot)
            overrides = set(route.sync.manual_overrides if route.sync else [])
            before_hash = self.components.route_manager.compute_route_hash(route)
            for field, value in snapshot.items():
                if field in overrides:
                    preserved += 1
                else:
                    setattr(route, field, value)
            route.source.source_snapshot = snapshot
            route.source.upstream_present = True
            route.source.last_pulled_at = pulled_at
            if route.lifecycle_status == "disabled":
                route.lifecycle_status = "active"
            after_hash = self.components.route_manager.compute_route_hash(route)
            if before_hash != after_hash:
                RouteService._mark_changed(route, previous=current)
                affected_ids.append(route.id)
            routes_by_id[route.id] = route
            updated += int(source_changed)
            unchanged += int(not source_changed)

        for source_id, current in by_source_id.items():
            if source_id in incoming_ids or current.source.upstream_present is False:
                continue
            route = current.model_copy(deep=True)
            route.source.upstream_present = False
            route.source.last_pulled_at = pulled_at
            route.lifecycle_status = "disabled"
            RouteService._mark_changed(route, previous=current)
            routes_by_id[route.id] = route
            affected_ids.append(route.id)
            missing += 1

        routes = sorted(routes_by_id.values(), key=lambda route: route.id)
        self.components.route_manager.replace_routes(routes)
        return {
            "created": created,
            "updated": updated,
            "unchanged": unchanged,
            "preserved_overrides": preserved,
            "upstream_missing": missing,
            "routes_count": len(routes),
            "affected_route_ids": sorted(set(affected_ids)),
            "last_pulled_at": pulled_at,
        }

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

    def _unique_route_key(self, name: str, route_id: int, used_keys: set[str]) -> str:
        manager = self.components.route_manager
        base = manager.normalize_route_key(name) or f"upstream.agent.{route_id}"
        candidate = base
        suffix = route_id
        while candidate in used_keys:
            candidate = f"{base}.{suffix}"
            suffix += 1
        return candidate
