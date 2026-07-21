"""Semantic overlap diagnostics for locally persisted Agents."""

import json
from pathlib import Path

import numpy as np

from intent_hub.config import Config
from intent_hub.models import ConflictPoint, DiagnosticResult, RouteOverlap
from intent_hub.services.llm_service import LLMService

try:
    import umap
except Exception:  # pragma: no cover
    umap = None


class DiagnosticService:
    def __init__(self, components, cache_path=None):
        self.components = components
        self.cache_path = Path(cache_path or Config.DIAGNOSTICS_CACHE_FILE)

    @staticmethod
    def _similarity(left, right):
        left = np.asarray(left, dtype=np.float32)
        right = np.asarray(right, dtype=np.float32)
        denominator = np.linalg.norm(left) * np.linalg.norm(right)
        return float(np.dot(left, right) / denominator) if denominator else 0.0

    def _active_synced(self):
        return {agent.id: agent for agent in self.components.agent_store.active() if agent.utterances}

    def analyze_route(self, route_id: int, max_conflicts=None):
        agents = self._active_synced()
        current = agents.get(route_id)
        if not current:
            raise ValueError("Agent 不存在、已停用或尚无正向语料")
        current_points = self.components.qdrant_client.get_route_vectors(route_id, exclude_negative=True)
        if not current_points:
            return DiagnosticResult(route_id=route_id, route_name=current.title)
        current_centroid = np.mean([point["vector"] for point in current_points], axis=0)
        overlaps = []
        for other_id, other in agents.items():
            if other_id == route_id:
                continue
            points = self.components.qdrant_client.get_route_vectors(other_id, exclude_negative=True)
            if not points:
                continue
            centroid_similarity = self._similarity(current_centroid, np.mean([point["vector"] for point in points], axis=0))
            conflicts = []
            for left in current_points:
                for right in points:
                    score = self._similarity(left["vector"], right["vector"])
                    if score >= Config.INSTANCE_THRESHOLD_AMBIGUOUS:
                        conflicts.append(ConflictPoint(source_utterance=left["payload"].get("utterance", ""), target_utterance=right["payload"].get("utterance", ""), similarity=score))
            conflicts.sort(key=lambda item: item.similarity, reverse=True)
            total = len(conflicts)
            if max_conflicts is not None:
                conflicts = conflicts[:max_conflicts]
            if centroid_similarity >= Config.REGION_THRESHOLD_SIGNIFICANT or conflicts:
                overlaps.append(RouteOverlap(target_route_id=other_id, target_route_name=other.title, region_similarity=centroid_similarity, instance_conflicts=conflicts, total_conflicts=total))
        overlaps.sort(key=lambda item: item.region_similarity, reverse=True)
        return DiagnosticResult(route_id=route_id, route_name=current.title, overlaps=overlaps)

    def analyze_all(self, refresh=False, max_conflicts=10):
        if not refresh and self.cache_path.exists():
            return [DiagnosticResult(**item) for item in json.loads(self.cache_path.read_text(encoding="utf-8"))]
        results = [self.analyze_route(agent.id, max_conflicts=max_conflicts) for agent in self._active_synced().values()]
        results = [result for result in results if result.overlaps]
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.cache_path.with_suffix(".tmp")
        temp.write_text(json.dumps([item.model_dump() for item in results], ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(self.cache_path)
        return results

    def umap_points(self, n_neighbors=15, min_dist=0.1, seed=42):
        if umap is None:
            raise RuntimeError("未安装 umap-learn")
        points = self.components.qdrant_client.scroll_all_points(with_vectors=True, exclude_negative=True)
        if len(points) < 2:
            return {"points": [], "meta": {"n_points": len(points), "n_neighbors": n_neighbors, "min_dist": min_dist}}
        if len(points) == 2:
            result = []
            for index, point in enumerate(points):
                payload = point["payload"]
                result.append({"x": float(index), "y": 0.0, "route_id": int(payload["route_id"]), "route_name": payload.get("route_name", ""), "utterance": payload.get("utterance", "")})
            return {"points": result, "meta": {"n_points": 2, "n_neighbors": 1, "min_dist": min_dist}}
        actual_neighbors = max(2, min(n_neighbors, len(points) - 1))
        projection = umap.UMAP(n_components=2, n_neighbors=actual_neighbors, min_dist=min_dist, metric="cosine", random_state=seed).fit_transform(np.asarray([p["vector"] for p in points]))
        result = []
        for coordinates, point in zip(projection, points):
            payload = point["payload"]
            result.append({"x": float(coordinates[0]), "y": float(coordinates[1]), "route_id": int(payload["route_id"]), "route_name": payload.get("route_name", ""), "utterance": payload.get("utterance", "")})
        return {"points": result, "meta": {"n_points": len(result), "n_neighbors": actual_neighbors, "min_dist": min_dist}}

    def repair(self, source_id, target_id):
        source = self.components.agent_store.get(source_id)
        target = self.components.agent_store.get(target_id)
        if not source or not target:
            raise ValueError("Agent 不存在")
        overlap = self.analyze_route(source_id)
        match = next((item for item in overlap.overlaps if item.target_route_id == target_id), None)
        conflicts = [f"{item.source_utterance} <> {item.target_utterance} ({item.similarity:.4f})" for item in (match.instance_conflicts if match else [])]
        return LLMService().repair(source, target, conflicts)

    def merge(self, source_id, target_id, title, text=""):
        source = self.components.agent_store.get(source_id)
        target = self.components.agent_store.get(target_id)
        if not source or not target:
            raise ValueError("Agent 不存在")
        merged = self.components.agent_store.create_local(
            title=title, text=text,
            utterances=list(dict.fromkeys(source.utterances + target.utterances)),
            negative_samples=list(dict.fromkeys(source.negative_samples + target.negative_samples)),
            score_threshold=max(source.score_threshold, target.score_threshold),
            negative_threshold=max(source.negative_threshold, target.negative_threshold),
        )
        self.components.agent_store.update(source_id, {"lifecycle_status": "inactive"})
        self.components.agent_store.update(target_id, {"lifecycle_status": "inactive"})
        return merged
