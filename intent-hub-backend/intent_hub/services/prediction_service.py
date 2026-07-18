"""Return the single highest-scoring Agent or the default text."""

from intent_hub.config import Config


class PredictionService:
    def __init__(self, component_manager):
        self.components = component_manager

    def route(self, query: str) -> dict:
        vector = self.components.encoder.encode_single(query)
        excluded = {
            result["payload"].get("route_id")
            for result in self.components.qdrant_client.search_negative_samples(vector)
            if result["score"]
            >= (
                self.components.agent_store.get(result["payload"].get("route_id")).negative_threshold
                if self.components.agent_store.get(result["payload"].get("route_id"))
                else Config.NEGATIVE_THRESHOLD
            )
        }
        for result in self.components.qdrant_client.search(vector):
            agent_id = result["payload"].get("route_id")
            if agent_id in excluded:
                continue
            agent = self.components.agent_store.get(agent_id)
            if agent and result["score"] >= agent.score_threshold:
                return {
                    "matched": True,
                    "agent": agent.details,
                    "score": float(result["score"]),
                    "text": None,
                }
        return {
            "matched": False,
            "agent": None,
            "score": None,
            "text": self._default_text(),
        }

    @staticmethod
    def _default_text() -> str:
        try:
            return Config.DEFAULT_ROUTE_FILE.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return "none"
