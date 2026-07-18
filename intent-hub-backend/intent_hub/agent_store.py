"""Local snapshot of Agents fetched from the upstream API."""

from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from intent_hub.models import Agent


class AgentStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = RLock()
        self._agents: dict[int, Agent] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            return
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self._agents = {item.id: item for item in (Agent(**raw) for raw in data)}

    def replace(self, agents: list[Agent]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(".tmp")
            temp.write_text(
                json.dumps([agent.model_dump() for agent in agents], ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temp.replace(self.path)
            self._agents = {agent.id: agent for agent in agents}

    def all(self) -> list[Agent]:
        with self._lock:
            return list(self._agents.values())

    def get(self, agent_id: int) -> Agent | None:
        with self._lock:
            return self._agents.get(agent_id)
