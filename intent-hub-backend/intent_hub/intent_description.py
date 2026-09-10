"""Versioned Agent definition text, separate from positive and negative corpus."""

import hashlib
import json


def description_text(agent) -> str:
    return f"名称：{agent.title.strip()}\n描述：{agent.text.strip()}"


def description_hash(agent, model_name: str) -> str:
    value = {"format": "intent-description-v1", "text": description_text(agent), "model": model_name}
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
