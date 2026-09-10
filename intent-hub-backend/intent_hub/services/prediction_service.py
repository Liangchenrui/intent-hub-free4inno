"""Return every Agent that reaches its routing threshold."""

from intent_hub.config import Config
from intent_hub.services.fallback_service import FallbackService


class PredictionService:
    def __init__(self, component_manager):
        self.components = component_manager

    def route(self, query: str) -> dict:
        vector = self.components.encoder.encode_single(query)
        agents = {agent.id: agent for agent in self.components.agent_store.active()}
        result_limit = max(1, len(agents))
        excluded = set()
        for result in self.components.qdrant_client.search_negative_samples(
            vector, top_k=result_limit
        ):
            agent_id = result["payload"].get("route_id")
            agent = agents.get(agent_id)
            threshold = agent.negative_threshold if agent else Config.NEGATIVE_THRESHOLD
            if result["score"] >= threshold:
                excluded.add(agent_id)

        matches_by_agent = {}
        for result in self.components.qdrant_client.search(vector, top_k=result_limit):
            agent_id = result["payload"].get("route_id")
            if agent_id in excluded:
                continue
            agent = agents.get(agent_id)
            if agent and result["score"] >= agent.score_threshold:
                score = float(result["score"])
                current = matches_by_agent.get(agent_id)
                if current is None or score > current["score"]:
                    matches_by_agent[agent_id] = {
                        "agent": agent.details,
                        "score": score,
                    }

        matches = sorted(matches_by_agent.values(), key=lambda item: item["score"], reverse=True)
        if matches:
            return {
                "matched": True,
                "agents": matches,
                "text": None,
                "match_source": "semantic",
                "fallback_status": None,
            }

        return FallbackService(self.components).predict(query, vector, excluded)
