"""Manage Qdrant collections and restore routed text from point payloads."""

import re
from collections import OrderedDict

from qdrant_client import QdrantClient

from intent_hub.config import Config
from intent_hub.models import Agent


COLLECTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class CollectionService:
    def __init__(self, components):
        self.components = components

    @staticmethod
    def _normalize_name(name: str) -> str:
        name = str(name or "").strip()
        if not name:
            raise ValueError("Collection 名称不能为空")
        if len(name) > 255 or not COLLECTION_NAME_PATTERN.fullmatch(name):
            raise ValueError("Collection 名称仅支持字母、数字、点、下划线和连字符")
        return name

    @staticmethod
    def _client() -> QdrantClient:
        return QdrantClient(
            url=Config.QDRANT_URL.strip().rstrip("/"),
            api_key=Config.QDRANT_API_KEY,
            timeout=30,
            check_compatibility=False,
        )

    def list_collections(self) -> dict:
        client = self._client()
        collections = [
            {"name": item.name, "kind": "collection", "target": None}
            for item in client.get_collections().collections
        ]
        aliases = [
            {
                "name": item.alias_name,
                "kind": "alias",
                "target": item.collection_name,
            }
            for item in client.get_aliases().aliases
        ]
        items = sorted(collections + aliases, key=lambda item: item["name"].lower())
        return {"current": Config.QDRANT_COLLECTION, "collections": items}

    def create_collection(self, name: str) -> dict:
        name = self._normalize_name(name)
        existing = {item["name"] for item in self.list_collections()["collections"]}
        if name in existing:
            raise ValueError("Collection 已存在")
        self.components.create_qdrant(name)
        return {"name": name, "kind": "collection", "target": None}

    def restore_collection(self, name: str) -> dict:
        name = self._normalize_name(name)
        available = {item["name"] for item in self.list_collections()["collections"]}
        if name not in available:
            raise ValueError("Collection 不存在")

        routes: OrderedDict[int, dict] = OrderedDict()
        points_count = skipped_points = 0
        client = self._client()
        offset = None
        while True:
            points, offset = client.scroll(
                collection_name=name,
                limit=256,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for point in points:
                points_count += 1
                payload = point.payload or {}
                try:
                    route_id = int(payload.get("route_id"))
                except (TypeError, ValueError):
                    skipped_points += 1
                    continue
                utterance = str(payload.get("utterance") or "").strip()
                if not utterance:
                    skipped_points += 1
                    continue
                route = routes.setdefault(route_id, {
                    "title": "",
                    "utterances": [],
                    "negative_samples": [],
                    "score_threshold": Config.SCORE_THRESHOLD,
                    "negative_threshold": Config.NEGATIVE_THRESHOLD,
                })
                route_name = str(payload.get("route_name") or "").strip()
                if route_name:
                    route["title"] = route_name
                if payload.get("is_negative") is True:
                    if utterance not in route["negative_samples"]:
                        route["negative_samples"].append(utterance)
                    if payload.get("negative_threshold") is not None:
                        route["negative_threshold"] = float(payload["negative_threshold"])
                else:
                    if utterance not in route["utterances"]:
                        route["utterances"].append(utterance)
                    if payload.get("score_threshold") is not None:
                        route["score_threshold"] = float(payload["score_threshold"])
            if offset is None:
                break

        restored_agents = 0
        for route_id, route in routes.items():
            current = self.components.agent_store.get(route_id)
            title = route["title"] or (current.title if current else f"Agent {route_id}")
            values = {
                "title": title,
                "utterances": route["utterances"],
                "negative_samples": route["negative_samples"],
                "score_threshold": route["score_threshold"],
                "negative_threshold": route["negative_threshold"],
                "lifecycle_status": "active",
            }
            if current:
                self.components.agent_store.update(route_id, values)
            else:
                self.components.agent_store.upsert(Agent(
                    id=route_id,
                    source_type="local",
                    title=title,
                    utterances=route["utterances"],
                    negative_samples=route["negative_samples"],
                    score_threshold=route["score_threshold"],
                    negative_threshold=route["negative_threshold"],
                    details={"restored_from_collection": name},
                ))
            restored_agents += 1

        Config.save_collection(name)
        self.components.reset_qdrant()
        return {
            "collection": name,
            "restored_agents": restored_agents,
            "positive_texts": sum(len(route["utterances"]) for route in routes.values()),
            "negative_texts": sum(len(route["negative_samples"]) for route in routes.values()),
            "points_count": points_count,
            "skipped_points": skipped_points,
        }
