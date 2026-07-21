"""Pull upstream Agents into the local SQLite repository."""

from intent_hub.agent_source import AgentSource
from intent_hub.agent_store import now_iso


class PullService:
    def __init__(self, component_manager, source=None):
        self.components = component_manager
        self.source = source or AgentSource()

    def pull(self) -> dict:
        agents = self.source.fetch_all()
        if not agents:
            return {"created": 0, "updated": 0, "preserved_overrides": 0, "disabled": 0, "agents_count": len(self.components.agent_store.all()), "warning": "上游未返回 Agent，本地数据保持不变"}
        result = self.components.agent_store.merge_upstream(agents)
        pulled_at = now_iso()
        self.components.agent_store.set_metadata("last_pull_at", pulled_at)
        result["last_pull_at"] = pulled_at
        return result
