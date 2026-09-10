"""Stable text and versioning for the entity-level retrieval index."""

import hashlib
import json

from intent_hub.models import RouteConfig


def description_text(route: RouteConfig) -> str:
    return f"名称：{route.name.strip()}\n描述：{route.description.strip()}"


def description_hash(route: RouteConfig, model_name: str) -> str:
    content = json.dumps(
        [1, model_name, description_text(route)], ensure_ascii=False
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
