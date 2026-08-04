"""JSON route import service."""

from intent_hub.models import RouteConfig
from intent_hub.services.route_service import RouteService


class ImportService:
    """Handle standard JSON route import into routes.json."""

    def __init__(self, component_manager):
        self.component_manager = component_manager
        self.route_service = RouteService(component_manager)

    def import_routes(
        self,
        routes: list[RouteConfig],
        mode: str = "merge",
        import_origin: str = "api_import",
    ) -> dict:
        mode = (mode or "merge").strip().lower()
        if mode not in ("merge", "replace"):
            raise ValueError("mode 仅支持 'merge' 或 'replace'")

        route_manager = self.component_manager.route_manager
        existing_routes = route_manager.get_all_routes()
        self._validate_payload(routes, existing_routes)
        existing_ids = {r.id for r in existing_routes}

        imported_ids: list[int] = []
        created = 0
        updated = 0

        for route in routes:
            prepared = self._prepare_imported_route(route, import_origin=import_origin)
            if prepared.id == 0:
                created_route = self.route_service.create_route(prepared)
                imported_ids.append(created_route.id)
                created += 1
                continue

            is_update = prepared.id in existing_ids
            saved_route = self.route_service.save_imported_route(prepared)
            imported_ids.append(saved_route.id)
            if is_update:
                updated += 1
            else:
                created += 1
                existing_ids.add(prepared.id)

        removed = 0
        if mode == "replace":
            imported_set = set(imported_ids)
            to_remove = [r.id for r in route_manager.get_all_routes() if r.id not in imported_set]
            for route_id in to_remove:
                self.route_service.delete_route(route_id)
                removed += 1

        return {
            "mode": mode,
            "created": created,
            "updated": updated,
            "removed": removed,
            "total": len(imported_ids),
            "conflicts": [],
            "affected_route_ids": list(dict.fromkeys(imported_ids + to_remove if mode == "replace" else imported_ids)),
        }

    def _validate_payload(
        self,
        routes: list[RouteConfig],
        existing_routes: list[RouteConfig],
    ) -> None:
        seen_ids: set[int] = set()
        seen_keys: set[str] = set()
        existing_by_id = {route.id: route for route in existing_routes}
        existing_by_key = {route.route_key: route for route in existing_routes}
        conflicts: list[str] = []

        for route in routes:
            normalized_key = self.component_manager.route_manager.normalize_route_key(route.route_key)
            if not normalized_key:
                raise ValueError("route_key is required")
            if normalized_key in seen_keys:
                raise ValueError(f"Duplicate route_key in import payload: {normalized_key}")
            seen_keys.add(normalized_key)

            if route.id != 0:
                if route.id in seen_ids:
                    raise ValueError(f"Duplicate route id in import payload: {route.id}")
                seen_ids.add(route.id)

            existing_same_key = existing_by_key.get(normalized_key)
            existing_same_id = existing_by_id.get(route.id) if route.id != 0 else None

            if route.id == 0 and existing_same_key is not None:
                conflicts.append(f"route_key 冲突: {normalized_key} 已存在 (id={existing_same_key.id})")
                continue

            if route.id != 0 and existing_same_key is not None and existing_same_key.id != route.id:
                conflicts.append(
                    f"route_key 冲突: {normalized_key} 已被其他路由占用 (id={existing_same_key.id})"
                )
                continue

            if route.id != 0 and existing_same_id is not None:
                managed_fields = (
                    set(existing_same_id.source.managed_fields)
                    if existing_same_id.source is not None
                    else set()
                )
                if "route_key" in managed_fields and existing_same_id.route_key != normalized_key:
                    conflicts.append(
                        f"托管字段冲突: route_id={route.id} 的 route_key 受托管，不能从 "
                        f"{existing_same_id.route_key} 改为 {normalized_key}"
                    )

        if conflicts:
            raise ValueError("; ".join(conflicts))

    @staticmethod
    def _prepare_imported_route(route: RouteConfig, import_origin: str) -> RouteConfig:
        route.source = RouteConfig.RouteSource(
            type="json_import",
            source_id=route.source.source_id if route.source else None,
            import_origin=route.source.import_origin if route.source and route.source.import_origin else import_origin,
            managed_fields=route.source.managed_fields if route.source else [],
        )
        route.lifecycle_status = route.lifecycle_status or "active"
        return route
