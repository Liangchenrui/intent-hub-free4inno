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

from intent_hub.intent_description import description_hash


class IntentHubQdrantClient:
    ROUTE_ID_KEY = "route_id"
    ROUTE_NAME_KEY = "route_name"
    UTTERANCE_KEY = "utterance"
    ROUTE_HASH_KEY = "route_hash"
    MODEL_NAME_KEY = "model_name"
    SCORE_THRESHOLD_KEY = "score_threshold"
    IS_NEGATIVE_KEY = "is_negative"
    NEGATIVE_THRESHOLD_KEY = "negative_threshold"
    IS_ROUTE_METADATA_KEY = "is_route_metadata"
    DESCRIPTION_HASH_KEY = "description_hash"

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
            (self.IS_ROUTE_METADATA_KEY, PayloadSchemaType.BOOL),
            (self.DESCRIPTION_HASH_KEY, PayloadSchemaType.KEYWORD),
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

    def clear(self) -> None:
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(must=[]),
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
        description_embedding: list[float] | None = None,
        description_version: str | None = None,
    ) -> list[PointStruct]:
        if len(utterances) != len(positive_embeddings):
            raise ValueError("utterances 和 embeddings 长度不匹配")
        if len(negative_samples) != len(negative_embeddings):
            raise ValueError("negative_samples 和 embeddings 长度不匹配")
        points = self._positive_points(
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
        if description_embedding is not None:
            if (len(description_embedding) != self.dimensions or not any(description_embedding)
                    or not description_version):
                raise ValueError("Invalid intent description embedding")
            points.append(PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"route-metadata:{route_id}")),
                vector=description_embedding,
                payload={self.ROUTE_ID_KEY: route_id, self.ROUTE_NAME_KEY: route_name,
                         self.IS_ROUTE_METADATA_KEY: True, self.ROUTE_HASH_KEY: route_hash,
                         self.DESCRIPTION_HASH_KEY: description_version, self.MODEL_NAME_KEY: model_name},
            ))
        return points

    def get_description_embedding(self, agent, model_name: str) -> list[float] | None:
        points = self.client.retrieve(
            collection_name=self.collection_name,
            ids=[str(uuid.uuid5(uuid.NAMESPACE_DNS, f"route-metadata:{agent.id}"))],
            with_payload=True, with_vectors=True,
        )
        if not points:
            return None
        point = points[0]
        if ((point.payload or {}).get(self.DESCRIPTION_HASH_KEY) == description_hash(agent, model_name)
                and isinstance(point.vector, list) and len(point.vector) == self.dimensions and any(point.vector)):
            return point.vector
        return None

    def search_route_descriptions(self, query_vector, route_ids, top_k=5) -> list[dict]:
        from qdrant_client.models import IsEmptyCondition, PayloadField

        if not route_ids:
            return []
        return self._search_grouped(query_vector, top_k, Filter(
            must=[FieldCondition(key=self.IS_ROUTE_METADATA_KEY, match=MatchValue(value=True)),
                  FieldCondition(key=self.ROUTE_ID_KEY, match=MatchAny(any=route_ids))],
            must_not=[IsEmptyCondition(is_empty=PayloadField(key=self.DESCRIPTION_HASH_KEY))],
        ))

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
        return self._search_grouped(
            query_vector,
            top_k,
            Filter(
                must_not=[FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)),
                          FieldCondition(key=self.IS_ROUTE_METADATA_KEY, match=MatchValue(value=True))]
            ),
        )

    def search_negative_samples(self, query_vector: list[float], top_k: int = 20) -> list[dict]:
        return self._search_grouped(
            query_vector,
            top_k,
            Filter(
                must=[FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True))]
            ),
        )

    def _search_grouped(
        self, query_vector: list[float], top_k: int, query_filter: Filter
    ) -> list[dict]:
        result = self.client.query_points_groups(
            collection_name=self.collection_name,
            query=query_vector,
            group_by=self.ROUTE_ID_KEY,
            group_size=1,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )
        return [
            {"score": group.hits[0].score, "payload": group.hits[0].payload or {}}
            for group in result.groups
            if group.hits
        ]

    @staticmethod
    def _point_dict(point) -> dict:
        vector = point.vector
        if isinstance(vector, dict):
            vector = next(iter(vector.values()), None)
        return {"id": str(point.id), "vector": vector, "payload": point.payload or {}}

    def get_route_vectors(self, route_id: int, exclude_negative: bool = False) -> list[dict]:
        must_not = [FieldCondition(key=self.IS_ROUTE_METADATA_KEY, match=MatchValue(value=True))]
        if exclude_negative:
            must_not.append(FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)))
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
        exclusions = [FieldCondition(key=self.IS_ROUTE_METADATA_KEY, match=MatchValue(value=True))]
        if exclude_negative:
            exclusions.append(FieldCondition(key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)))
        route_filter = Filter(must_not=exclusions)
        result, offset = [], None
        while True:
            points, offset = self.client.scroll(collection_name=self.collection_name, limit=256, offset=offset, scroll_filter=route_filter, with_payload=True, with_vectors=with_vectors)
            result.extend(self._point_dict(point) for point in points)
            if offset is None:
                return result
