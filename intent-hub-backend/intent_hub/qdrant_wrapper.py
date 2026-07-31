"""Qdrant operations used by the minimal Agent router."""

from __future__ import annotations

import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CreateAlias,
    CreateAliasOperation,
    DeleteAlias,
    DeleteAliasOperation,
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)


class IntentHubQdrantClient:
    ROUTE_ID_KEY = "route_id"
    ROUTE_NAME_KEY = "route_name"
    UTTERANCE_KEY = "utterance"
    ROUTE_HASH_KEY = "route_hash"
    MODEL_NAME_KEY = "model_name"
    SCORE_THRESHOLD_KEY = "score_threshold"
    IS_NEGATIVE_KEY = "is_negative"
    NEGATIVE_THRESHOLD_KEY = "negative_threshold"

    def __init__(self, url: str, collection_name: str, dimensions: int, api_key: str | None = None):
        self.collection_name = collection_name
        self.client = QdrantClient(url=url.strip().rstrip("/"), api_key=api_key, timeout=600)
        self.dimensions = dimensions
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=self.dimensions, distance=Distance.COSINE),
            )
        for field, schema in (
            (self.ROUTE_ID_KEY, PayloadSchemaType.INTEGER),
            (self.IS_NEGATIVE_KEY, PayloadSchemaType.BOOL),
        ):
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema=schema,
                )
            except Exception as error:
                if "already exists" not in str(error).lower():
                    raise

    @staticmethod
    def point_ids(
        route_id: int,
        route_name: str,
        utterances: list[str],
        negative_samples: list[str],
        *,
        legacy: bool = False,
    ) -> set[str]:
        if legacy:
            positive = (f"{route_id}:{route_name}:{text}" for text in utterances)
            negative = (f"negative:{route_id}:{route_name}:{text}" for text in negative_samples)
        else:
            positive = (f"positive:{route_id}:{text}" for text in utterances)
            negative = (f"negative:{route_id}:{text}" for text in negative_samples)
        return {str(uuid.uuid5(uuid.NAMESPACE_DNS, value)) for value in (*positive, *negative)}

    def delete_routes(self, route_ids: set[int]) -> None:
        if route_ids:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=self.ROUTE_ID_KEY,
                            match=MatchAny(any=sorted(route_ids)),
                        )
                    ]
                ),
                wait=True,
            )

    def upsert_routes(self, routes: list[dict], batch_size: int = 128) -> None:
        points = []
        for route in routes:
            points.extend(self._route_points(**route))
        for start in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=self.collection_name,
                points=points[start : start + batch_size],
                wait=True,
            )

    def switch_alias(self, alias_name: str) -> None:
        aliases = self.client.get_aliases().aliases
        operations = []
        if any(alias.alias_name == alias_name for alias in aliases):
            operations.append(DeleteAliasOperation(delete_alias=DeleteAlias(alias_name=alias_name)))
        operations.append(
            CreateAliasOperation(
                create_alias=CreateAlias(
                    collection_name=self.collection_name,
                    alias_name=alias_name,
                )
            )
        )
        self.client.update_collection_aliases(change_aliases_operations=operations)

    def index_summary(self) -> dict:
        route_ids = set()
        route_hashes = {}
        points_count = 0
        offset = None
        while True:
            points, offset = self.client.scroll(
                collection_name=self.collection_name,
                limit=200,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            points_count += len(points)
            for point in points:
                payload = point.payload or {}
                route_id = payload.get(self.ROUTE_ID_KEY)
                if route_id is not None:
                    route_ids.add(route_id)
                    if payload.get(self.ROUTE_HASH_KEY):
                        route_hashes[route_id] = payload[self.ROUTE_HASH_KEY]
            if offset is None:
                break
        return {
            "points_count": points_count,
            "route_ids": sorted(route_ids),
            "route_hashes": route_hashes,
        }

    def _route_points(
        self,
        route_id: int,
        route_name: str,
        utterances: list[str],
        positive_embeddings: list[list[float]],
        negative_samples: list[str],
        negative_embeddings: list[list[float]],
        score_threshold: float,
        negative_threshold: float,
        route_hash: str,
        model_name: str,
    ) -> list[PointStruct]:
        if len(utterances) != len(positive_embeddings):
            raise ValueError("utterances 和 embeddings 长度不匹配")
        if len(negative_samples) != len(negative_embeddings):
            raise ValueError("negative_samples 和 embeddings 长度不匹配")
        return self._positive_points(
            route_id,
            route_name,
            utterances,
            positive_embeddings,
            score_threshold,
            route_hash,
            model_name,
        ) + self._negative_points(
            route_id,
            route_name,
            negative_samples,
            negative_embeddings,
            negative_threshold,
        )

    def _positive_points(
        self,
        route_id,
        route_name,
        utterances,
        embeddings,
        score_threshold,
        route_hash,
        model_name,
    ) -> list[PointStruct]:
        points = []
        for utterance, embedding in zip(utterances, embeddings):
            payload = {
                self.ROUTE_ID_KEY: route_id,
                self.ROUTE_NAME_KEY: route_name,
                self.UTTERANCE_KEY: utterance,
                self.SCORE_THRESHOLD_KEY: score_threshold,
            }
            if route_hash:
                payload[self.ROUTE_HASH_KEY] = route_hash
            if model_name:
                payload[self.MODEL_NAME_KEY] = model_name
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"positive:{route_id}:{utterance}")),
                    vector=embedding,
                    payload=payload,
                )
            )
        return points

    def _negative_points(
        self,
        route_id,
        route_name,
        negative_samples,
        embeddings,
        negative_threshold,
    ) -> list[PointStruct]:
        return [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"negative:{route_id}:{text}")),
                vector=embedding,
                payload={
                    self.ROUTE_ID_KEY: route_id,
                    self.ROUTE_NAME_KEY: route_name,
                    self.UTTERANCE_KEY: text,
                    self.IS_NEGATIVE_KEY: True,
                    self.NEGATIVE_THRESHOLD_KEY: negative_threshold,
                },
            )
            for text, embedding in zip(negative_samples, embeddings)
        ]

    def search(self, query_vector: list[float], top_k: int = 20) -> list[dict]:
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=Filter(
                must_not=[FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True))]
            ),
            with_payload=True,
        )
        return [{"score": point.score, "payload": point.payload or {}} for point in result.points]

    def search_negative_samples(self, query_vector: list[float], top_k: int = 20) -> list[dict]:
        result = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=Filter(
                must=[FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True))]
            ),
            with_payload=True,
        )
        return [{"score": point.score, "payload": point.payload or {}} for point in result.points]

    @staticmethod
    def _point_dict(point) -> dict:
        vector = point.vector
        if isinstance(vector, dict):
            vector = next(iter(vector.values()), None)
        return {"id": str(point.id), "vector": vector, "payload": point.payload or {}}

    def get_route_vectors(self, route_id: int, exclude_negative: bool = False) -> list[dict]:
        must_not = [FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True))] if exclude_negative else None
        points, offset = self.client.scroll(
            collection_name=self.collection_name, limit=256,
            scroll_filter=Filter(must=[FieldCondition(key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id))], must_not=must_not),
            with_payload=True, with_vectors=True,
        )
        result = [self._point_dict(point) for point in points]
        while offset is not None:
            points, offset = self.client.scroll(collection_name=self.collection_name, limit=256, offset=offset, scroll_filter=Filter(must=[FieldCondition(key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id))], must_not=must_not), with_payload=True, with_vectors=True)
            result.extend(self._point_dict(point) for point in points)
        return result

    def scroll_all_points(self, with_vectors: bool = True, exclude_negative: bool = False) -> list[dict]:
        route_filter = Filter(must_not=[FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True))]) if exclude_negative else None
        result, offset = [], None
        while True:
            points, offset = self.client.scroll(collection_name=self.collection_name, limit=256, offset=offset, scroll_filter=route_filter, with_payload=True, with_vectors=with_vectors)
            result.extend(self._point_dict(point) for point in points)
            if offset is None:
                return result
