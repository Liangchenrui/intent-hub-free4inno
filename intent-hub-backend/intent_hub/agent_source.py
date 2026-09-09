"""Read-only client for the upstream Agent API."""

import ast
import json
from typing import Any

import requests

from intent_hub.config import Config
from intent_hub.models import Agent


class AgentSource:
    LABEL_IDS = (87, 88, 89)

    def __init__(self, session=None):
        self.session = session or requests.Session()

    def fetch_all(self) -> list[Agent]:
        records_by_id = {}
        for label_id in self.LABEL_IDS:
            for record in self._get(
                "/resource/search", params={"labels": str(label_id)}
            ).get("records", []):
                resource_id = (record.get("resource") or {}).get("id")
                if resource_id is not None:
                    records_by_id[resource_id] = record

        agents = []
        for record in records_by_id.values():
            resource = record.get("resource") or {}
            resource_id = resource.get("id")
            if resource_id is None:
                continue
            details = self._get(f"/resource/{resource_id}/detail")
            agents.append(
                Agent(
                    id=details["id"],
                    title=details.get("title") or "",
                    text=details.get("text") or "",
                    utterances=self._parse_corpus(details.get("extent00")),
                    negative_samples=self._parse_corpus(details.get("extent01")),
                    details=details,
                )
            )
        return agents

    def _get(self, path: str, params=None) -> dict[str, Any]:
        token = str(Config.AGENT_API_TOKEN or "").strip()
        if not token:
            raise RuntimeError("AGENT_API_TOKEN 未在运行环境中配置")
        response = self.session.get(
            f"{Config.AGENT_API_URL}{path}",
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
