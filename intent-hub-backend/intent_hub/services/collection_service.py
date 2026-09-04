"""List and create Qdrant collections without changing the active collection."""

import re

import requests

from intent_hub.config import Config
from intent_hub.qdrant_wrapper import IntentHubQdrantClient


COLLECTION_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


class CollectionService:
    def __init__(self, components=None, client_factory=IntentHubQdrantClient):
        self.components = components
        self.client_factory = client_factory

    @staticmethod
    def normalize_name(name: str) -> str:
        value = str(name or "").strip()
        if not value:
            raise ValueError("Collection 名称不能为空")
        if len(value) > 255 or not COLLECTION_NAME_PATTERN.fullmatch(value):
            raise ValueError("Collection 名称仅支持字母、数字、点、下划线和连字符")
        return value

    def list_collections(self) -> dict:
        base_url = Config.QDRANT_URL.rstrip("/")
        headers = {"api-key": Config.QDRANT_API_KEY} if Config.QDRANT_API_KEY else {}
        collections_response = requests.get(
            f"{base_url}/collections", headers=headers, timeout=10
        )
        collections_response.raise_for_status()
        collections = [
            {"name": item["name"], "kind": "collection", "target": None}
            for item in collections_response.json().get("result", {}).get("collections", [])
            if isinstance(item, dict) and item.get("name")
        ]

        aliases_response = requests.get(f"{base_url}/aliases", headers=headers, timeout=10)
        aliases_response.raise_for_status()
        aliases = [
            {
                "name": item["alias_name"],
                "kind": "alias",
                "target": item.get("collection_name"),
            }
            for item in aliases_response.json().get("result", {}).get("aliases", [])
            if isinstance(item, dict) and item.get("alias_name")
        ]
        options = sorted(collections + aliases, key=lambda item: item["name"].lower())
        return {
            "current": Config.QDRANT_COLLECTION,
            "collections": options,
            "items": [item["name"] for item in options],
        }

    def create_collection(self, name: str) -> dict:
        name = self.normalize_name(name)
        existing = {item["name"] for item in self.list_collections()["collections"]}
        if name in existing:
            raise ValueError("Collection 已存在")
        if self.components is None:
            raise RuntimeError("缺少运行组件，无法创建 Collection")
        self.client_factory(
            url=Config.QDRANT_URL,
            collection_name=name,
            dimensions=self.components.encoder.dimensions,
            api_key=Config.QDRANT_API_KEY,
            timeout=Config.QDRANT_TIMEOUT_SECONDS,
            write_batch_size=Config.QDRANT_WRITE_BATCH_SIZE,
        )
        return {"name": name, "kind": "collection", "target": None}
