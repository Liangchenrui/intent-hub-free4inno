"""Fetch every Agent and rebuild the configured Qdrant collection."""

import hashlib
import json

from intent_hub.agent_source import AgentSource
from intent_hub.config import Config


def agent_hash(agent) -> str:
    return hashlib.md5(
        json.dumps(agent.model_dump(), ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


class SyncService:
    def __init__(self, component_manager, source=None):
        self.components = component_manager
        self.source = source or AgentSource()

    def sync(self) -> dict:
        existing = {agent.id: agent for agent in self.components.agent_store.all()}
        agents = self.source.fetch_all()
        for agent in agents:
            if agent.id in existing:
                agent.score_threshold = existing[agent.id].score_threshold
                agent.negative_threshold = existing[agent.id].negative_threshold
        # Upstream data remains useful even when vector indexing fails.
        self.components.agent_store.replace(agents)
        encoded = []
        for agent in agents:
            if not agent.utterances:
                continue
            encoded.append(
                (
                    agent,
                    self.components.encoder.encode(agent.utterances),
                    self.components.encoder.encode(agent.negative_samples),
                )
            )

        qdrant = self.components.qdrant_client
        qdrant.delete_all()
        positive_count = 0
        negative_count = 0
        for agent, positives, negatives in encoded:
            route_hash = agent_hash(agent)
            qdrant.upsert_route_utterances(
                route_id=agent.id,
                route_name=agent.title,
                utterances=agent.utterances,
                embeddings=positives,
                score_threshold=agent.score_threshold,
                route_hash=route_hash,
                model_name=Config.EMBEDDING_MODEL_NAME,
            )
            positive_count += len(agent.utterances)
            if agent.negative_samples:
                qdrant.upsert_route_negative_samples(
                    route_id=agent.id,
                    route_name=agent.title,
                    negative_samples=agent.negative_samples,
                    embeddings=negatives,
                    negative_threshold=agent.negative_threshold,
                )
                negative_count += len(agent.negative_samples)

        result = {
            "agents_count": len(agents),
            "indexed_agents_count": len(encoded),
            "positive_points": positive_count,
            "negative_points": negative_count,
        }
        if not agents:
            result["warning"] = "上游没有包含指定标签的 Agent"
        elif not encoded:
            result["warning"] = "上游 Agent 没有正向语料（extent00），未生成向量"
        return result

    def update_thresholds(
        self, agent_id: int, score_threshold: float, negative_threshold: float
    ):
        current = self.components.agent_store.get(agent_id)
        if current is None:
            raise ValueError("Agent 不存在")
        updated = current.model_copy(
            update={
                "score_threshold": score_threshold,
                "negative_threshold": negative_threshold,
            }
        )
        self.components.qdrant_client.update_route_thresholds(
            route_id=agent_id,
            score_threshold=score_threshold,
            negative_threshold=negative_threshold,
            route_hash=agent_hash(updated),
        )
        agents = [updated if agent.id == agent_id else agent for agent in self.components.agent_store.all()]
        self.components.agent_store.replace(agents)
        return updated

    def status(self) -> dict:
        indexed_agents = [agent for agent in self.components.agent_store.all() if agent.utterances]
        expected_hashes = {agent.id: agent_hash(agent) for agent in indexed_agents}
        expected_points = sum(
            len(agent.utterances) + len(agent.negative_samples) for agent in indexed_agents
        )
        actual = self.components.qdrant_client.index_summary()
        synced = (
            bool(indexed_agents)
            and actual["points_count"] == expected_points
            and actual["route_ids"] == sorted(expected_hashes)
            and actual["route_hashes"] == expected_hashes
        )
        return {
            "agents_count": len(self.components.agent_store.all()),
            "collection": Config.QDRANT_COLLECTION,
            "expected_points": expected_points,
            "points_count": actual["points_count"],
            "synced": synced,
        }
