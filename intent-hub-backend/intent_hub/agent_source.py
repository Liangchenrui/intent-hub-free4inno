"""Read-only adapter for the optional upstream Agent API."""

import ast
import json
from typing import Any

import requests

from intent_hub.config import Config


class AgentSource:
    def __init__(self, session=None):
        self.session = session or requests.Session()

    def fetch_all(self) -> list[dict[str, Any]]:
        base_url = str(Config.AGENT_API_URL or "").strip().rstrip("/")
        token = str(Config.AGENT_API_TOKEN or "").strip()
        label_ids = [item.strip() for item in str(Config.AGENT_API_LABEL_IDS or "").split(",") if item.strip()]
        if not base_url or not token or not label_ids:
            raise ValueError("请先配置 AGENT_API_URL、AGENT_API_TOKEN 和 AGENT_API_LABEL_IDS")

        records_by_id: dict[str, dict] = {}
        for label_id in label_ids:
            payload = self._get(base_url, token, "/resource/search", {"labels": label_id})
            for record in payload.get("records", []):
                resource_id = (record.get("resource") or {}).get("id")
                if resource_id is not None:
                    records_by_id[str(resource_id)] = record

        agents = []
        for source_id in records_by_id:
            details = self._get(base_url, token, f"/resource/{source_id}/detail")
            agents.append(
                {
                    "source_id": str(details.get("id", source_id)),
                    "name": str(details.get("title") or "").strip(),
                    "description": str(details.get("text") or "").strip(),
                    "utterances": self._parse_corpus(details.get("extent00")),
                    "negative_samples": self._parse_corpus(details.get("extent01")),
                }
            )
        return agents

    def _get(self, base_url: str, token: str, path: str, params=None) -> dict[str, Any]:
        response = self.session.get(
            f"{base_url}{path}",
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
            raise RuntimeError(payload.get("msg") or "上游 Agent API 返回异常")
        return payload["data"]

    @staticmethod
    def _parse_corpus(value: Any) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str) and value.strip():
            try:
                items = json.loads(value)
            except json.JSONDecodeError:
                try:
                    items = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    return []
        else:
            return []
        if not isinstance(items, list):
            return []
        return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))
