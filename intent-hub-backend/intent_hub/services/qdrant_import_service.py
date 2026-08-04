"""Recover local intent route definitions from Qdrant point payloads."""

from collections import defaultdict
from typing import Any
from urllib.parse import quote

import requests

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.route_manager import RouteManager


class QdrantImportService:
    def __init__(self, route_manager: RouteManager):
        self.route_manager = route_manager

    def import_collection(self, collection: str) -> list[RouteConfig]:
        points = self._scroll_payloads(collection)
        routes = self._build_routes(points, collection)
        if not routes:
            raise ValueError(f"Collection {collection} 中没有可恢复的意图实体 payload")
        self.route_manager.replace_routes(routes)
        return routes

    @staticmethod
    def _scroll_payloads(collection: str) -> list[dict[str, Any]]:
        encoded_collection = quote(collection, safe="")
        url = f"{Config.QDRANT_URL.rstrip('/')}/collections/{encoded_collection}/points/scroll"
        headers = {"api-key": Config.QDRANT_API_KEY} if Config.QDRANT_API_KEY else {}
        points: list[dict[str, Any]] = []
        offset: Any = None

        while True:
            body: dict[str, Any] = {
                "limit": 256,
                "with_payload": True,
                "with_vector": False,
            }
            if offset is not None:
                body["offset"] = offset
            response = requests.post(url, headers=headers, json=body, timeout=30)
            response.raise_for_status()
            result = response.json().get("result", {})
            points.extend(result.get("points", []))
            offset = result.get("next_page_offset")
            if offset is None:
                return points

    def _build_routes(
        self, points: list[dict[str, Any]], collection: str
    ) -> list[RouteConfig]:
        metadata_routes: dict[int, RouteConfig] = {}
        grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
        for point in points:
            payload = point.get("payload") or {}
            if payload.get("is_route_metadata") is True:
                route_data = payload.get("route_config")
                if isinstance(route_data, dict):
                    try:
                        route = RouteConfig.model_validate(route_data)
                        metadata_routes[route.id] = route
                    except Exception:
                        pass
                continue
            route_id = payload.get("route_id")
            if isinstance(route_id, int) and payload.get("route_name") and payload.get("utterance"):
                grouped[route_id].append(payload)

        existing_by_name = {route.name: route for route in self.route_manager.get_all_routes()}
        used_keys: set[str] = set()
        routes: list[RouteConfig] = list(metadata_routes.values())
        used_keys.update(route.route_key for route in routes)
        for route_id, payloads in sorted(grouped.items()):
            if route_id in metadata_routes:
                continue
            first = payloads[0]
            name = str(first["route_name"])
            existing = existing_by_name.get(name)
            base_key = (
                existing.route_key
                if existing
                else self.route_manager.normalize_route_key(name) or f"route.{route_id}"
            )
            route_key = base_key
            suffix = route_id
            while route_key in used_keys:
                route_key = f"{base_key}.{suffix}"
                suffix += 1
            used_keys.add(route_key)

            positive = list(dict.fromkeys(
                str(payload["utterance"])
                for payload in payloads
                if not payload.get("is_negative", False)
            ))
            negative = list(dict.fromkeys(
                str(payload["utterance"])
                for payload in payloads
                if payload.get("is_negative", False)
            ))
            if not positive:
                continue

            routes.append(
                RouteConfig(
                    id=route_id,
                    name=name,
                    route_key=route_key,
                    description=existing.description if existing else "",
                    utterances=positive,
                    negative_samples=negative,
                    score_threshold=float(first.get("score_threshold", 0.75)),
                    negative_threshold=float(
                        next(
                            (
                                payload.get("negative_threshold", 0.95)
                                for payload in payloads
                                if payload.get("is_negative", False)
                            ),
                            0.95,
                        )
                    ),
                    source=RouteConfig.RouteSource(
                        type="json_import",
                        source_id=collection,
                        import_origin=f"qdrant:{collection}",
                        managed_fields=[
                            "name",
                            "utterances",
                            "negative_samples",
                            "score_threshold",
                            "negative_threshold",
                        ],
                    ),
                    sync=RouteConfig.RouteSync(status="synced"),
                )
            )
        return sorted(routes, key=lambda route: route.id)
