"""Qdrant客户端封装模块"""

import uuid
from urllib.parse import urlsplit
from typing import Any, Dict, List, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

from intent_hub.utils.logger import logger
from intent_hub.models import RouteConfig


class IntentHubQdrantClient:
    """Intent Hub专用的Qdrant客户端封装"""

    # Qdrant payload中的字段名
    ROUTE_ID_KEY = "route_id"
    ROUTE_NAME_KEY = "route_name"
    UTTERANCE_KEY = "utterance"
    ROUTE_HASH_KEY = "route_hash"
    MODEL_NAME_KEY = "model_name"
    SCORE_THRESHOLD_KEY = "score_threshold"
    IS_NEGATIVE_KEY = "is_negative"  # 标识是否为负例向量
    NEGATIVE_THRESHOLD_KEY = "negative_threshold"  # 负例阈值
    IS_ROUTE_METADATA_KEY = "is_route_metadata"
    ROUTE_CONFIG_KEY = "route_config"

    def __init__(
        self,
        url: str,
        collection_name: str,
        dimensions: int,
        api_key: Optional[str] = None,
        timeout: int = 30,
    ):
        """初始化Qdrant客户端

        Args:
            url: Qdrant服务地址
            collection_name: Collection名称
            dimensions: 向量维度
            api_key: API密钥（可选）
        """
        # QDRANT_URL is a complete URL. Never split it into host/port fields or
        # let the SDK silently append its default port.
        self.url = url.strip().rstrip("/") if url else ""
        parsed_url = urlsplit(self.url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("QDRANT_URL must be a complete http(s) URL")
        self.collection_name = collection_name
        self.dimensions = dimensions
        self.api_key = api_key

        try:
            clean_url = self.url
            # qdrant-client defaults to port 6333 even when a complete URL is
            # supplied without an explicit port. Preserve normal HTTP(S)
            # gateway semantics instead of silently bypassing the configured
            # reverse proxy.
            sdk_port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)

            logger.info(f"Initializing Qdrant client (URL mode) with: {clean_url}")
            self.client = QdrantClient(
                url=clean_url,
                port=sdk_port,
                api_key=api_key,
                timeout=timeout,
            )
            logger.info(f"Qdrant initialized (URL mode): {clean_url}")
        except Exception as e:
            if "SSL" in str(e) or "EOF" in str(e):
                logger.error(
                    "Qdrant SSL error. Check port (usually 443 for cloud) and proxy settings."
                )
            logger.error(f"Qdrant initialization failed: {e}", exc_info=True)
            raise

        self._ensure_collection()

    def _ensure_collection(self):
        """确保Collection存在，不存在则创建"""
        try:
            try:
                exists = self.client.collection_exists(self.collection_name)
            except Exception as e:
                logger.error(f"Error checking collection {self.collection_name}: {e}")
                raise RuntimeError(
                    f"Unable to verify Qdrant collection {self.collection_name}"
                ) from e

            if not exists:
                logger.info(f"Creating collection: {self.collection_name}")
                try:
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=VectorParams(
                            size=self.dimensions, distance=Distance.COSINE
                        ),
                    )
                    logger.info(f"Collection created: {self.collection_name}")
                except Exception as e:
                    # 再次捕获 409 Conflict 或 "already exists" 错误，防止并发导致的初始化失败
                    if "already exists" in str(e).lower() or "409" in str(e):
                        logger.info(f"Collection {self.collection_name} already exists")
                    else:
                        raise
            else:
                logger.info(f"Collection exists: {self.collection_name}")

            # 确保关键字段有索引 (针对 Qdrant Cloud 的性能或强制要求)
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self.ROUTE_ID_KEY,
                    field_schema=PayloadSchemaType.INTEGER,
                )
                logger.info(f"Index for {self.ROUTE_ID_KEY} ensured")
            except Exception as e:
                if (
                    "already exists" not in str(e).lower()
                    and "duplicate" not in str(e).lower()
                ):
                    logger.warning(
                        f"Warning creating index for {self.ROUTE_ID_KEY}: {e}"
                    )

            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self.IS_NEGATIVE_KEY,
                    field_schema=PayloadSchemaType.BOOL,
                )
                logger.info(f"Index for {self.IS_NEGATIVE_KEY} ensured")
            except Exception as e:
                if (
                    "already exists" not in str(e).lower()
                    and "duplicate" not in str(e).lower()
                ):
                    logger.warning(
                        f"Warning creating index for {self.IS_NEGATIVE_KEY}: {e}"
                    )

            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=self.IS_ROUTE_METADATA_KEY,
                    field_schema=PayloadSchemaType.BOOL,
                )
                logger.info(f"Index for {self.IS_ROUTE_METADATA_KEY} ensured")
            except Exception as e:
                if (
                    "already exists" not in str(e).lower()
                    and "duplicate" not in str(e).lower()
                ):
                    logger.warning(
                        f"Warning creating index for {self.IS_ROUTE_METADATA_KEY}: {e}"
                    )

        except Exception as e:
            logger.error(f"Collection initialization failed: {e}", exc_info=True)
            raise

    def upsert_route_utterances(
        self,
        route_id: int,
        route_name: str,
        utterances: List[str],
        embeddings: List[List[float]],
        score_threshold: float,
        route_hash: Optional[str] = None,  # 新增：路由哈希
        model_name: Optional[str] = None,  # 新增：模型名称
    ):
        """插入或更新路由的utterances向量

        Args:
            route_id: 路由ID
            route_name: 路由名称
            utterances: 示例语句列表
            embeddings: 对应的向量列表
            score_threshold: 相似度阈值
            route_hash: 路由配置的哈希值
            model_name: 当前使用的 Embedding 模型名称
        """
        if len(utterances) != len(embeddings):
            raise ValueError("utterances和embeddings长度不匹配")

        points = []
        for utterance, embedding in zip(utterances, embeddings):
            # 使用确定性UUID生成point ID
            point_id = str(
                uuid.uuid5(uuid.NAMESPACE_DNS, f"{route_id}:{route_name}:{utterance}")
            )

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

            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Updated route {route_name}: {len(points)} vectors")
        except Exception as e:
            logger.error(f"Failed to update vector points: {e}", exc_info=True)
            raise

    def delete_route(self, route_id: int):
        """删除指定路由的所有向量点

        Args:
            route_id: 路由ID
        """
        try:
            # 注意：Qdrant的FieldCondition需要匹配数值类型，这里使用MatchValue
            from qdrant_client.models import MatchValue

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                        )
                    ]
                ),
            )
            logger.info(f"Deleted points for route ID {route_id}")
        except Exception as e:
            logger.error(f"Failed to delete points: {e}", exc_info=True)
            raise

    def upsert_route_metadata(
        self,
        route: RouteConfig,
        route_hash: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> None:
        """Store a complete recovery-only RouteConfig point.

        The point is marked and every query/diagnostic path explicitly excludes it.
        Its vector exists only because Qdrant collections require one.
        """
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"route-metadata:{route.id}"))
        payload = {
            self.ROUTE_ID_KEY: route.id,
            self.ROUTE_NAME_KEY: route.name,
            self.IS_ROUTE_METADATA_KEY: True,
            self.ROUTE_CONFIG_KEY: route.model_dump(),
        }
        if route_hash:
            payload[self.ROUTE_HASH_KEY] = route_hash
        if model_name:
            payload[self.MODEL_NAME_KEY] = model_name
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=[0.0] * self.dimensions,
                    payload=payload,
                )
            ],
        )
        logger.info(f"Stored recovery metadata for route {route.name} (ID: {route.id})")

    def get_route_vectors(self, route_id: int) -> List[Dict[str, Any]]:
        """获取指定路由的所有向量点和载荷（排除负例向量）

        Args:
            route_id: 路由ID

        Returns:
            包含vector和payload的列表（仅包含正例向量）
        """
        try:
            from qdrant_client.models import MatchValue

            results = []
            offset = None
            batch_size = 100

            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    scroll_filter=Filter(
                        must=[
                            FieldCondition(
                                key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                            )
                        ],
                        # 排除负例向量：is_negative 不为 True
                        must_not=[
                            FieldCondition(
                                key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                            ),
                            FieldCondition(
                                key=self.IS_ROUTE_METADATA_KEY,
                                match=MatchValue(value=True),
                            ),
                        ],
                    ),
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=True,
                )

                points, next_offset = result
                for point in points:
                    # 双重检查：确保不是负例向量（兼容旧数据，如果 is_negative 字段不存在，也认为是正例）
                    payload = point.payload or {}
                    is_negative = payload.get(self.IS_NEGATIVE_KEY, False)
                    if not is_negative:
                        results.append({"vector": point.vector, "payload": payload})

                if next_offset is None:
                    break
                offset = next_offset

            return results
        except Exception as e:
            logger.error(
                f"Failed to get vectors for route {route_id}: {e}", exc_info=True
            )
            raise

    def search(self, query_vector: List[float], top_k: int = 1) -> List[Dict[str, Any]]:
        """搜索最相似的向量

        Args:
            query_vector: 查询向量
            top_k: 返回Top K结果

        Returns:
            搜索结果列表，每个结果包含score和payload
        """
        try:
            from qdrant_client.models import MatchValue

            return self._search_grouped(
                query_vector=query_vector,
                top_k=top_k,
                query_filter=Filter(
                    must_not=[
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        ),
                        FieldCondition(
                            key=self.IS_ROUTE_METADATA_KEY,
                            match=MatchValue(value=True),
                        ),
                    ]
                ),
            )
        except Exception as e:
            logger.error(f"Vector search failed: {e}", exc_info=True)
            raise

    def _search_grouped(
        self,
        query_vector: List[float],
        top_k: int,
        query_filter: Filter,
    ) -> List[Dict[str, Any]]:
        """Return the best matching point for each route."""
        results = self.client.query_points_groups(
            collection_name=self.collection_name,
            query=query_vector,
            group_by=self.ROUTE_ID_KEY,
            group_size=1,
            limit=top_k,
            query_filter=query_filter,
            with_payload=True,
        )

        search_results = []
        for group in results.groups:
            if not group.hits:
                continue
            point = group.hits[0]
            search_results.append(
                {
                    "score": point.score,
                    "payload": point.payload or {},
                }
            )
        return search_results

    def delete_all(self):
        """清空Collection中的所有向量点"""
        try:
            self.client.delete_collection(self.collection_name)
            self._ensure_collection()
            logger.info(f"Collection cleared: {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to clear collection: {e}", exc_info=True)
            raise

    def is_ready(self) -> bool:
        """检查Qdrant服务是否可用"""
        try:
            return self.client.collection_exists(self.collection_name)
        except Exception:
            return False

    def has_data(self) -> bool:
        """检查Collection中是否有数据"""
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count > 0
        except Exception as e:
            logger.error(f"Failed to check collection data: {e}", exc_info=True)
            return False

    def get_existing_route_ids(self) -> set[int]:
        """获取Qdrant中所有现有的路由ID集合

        Returns:
            路由ID集合
        """
        try:
            route_ids = set()
            # 使用scroll方法遍历所有点，提取唯一的route_id
            offset = None
            batch_size = 100

            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, next_offset = result

                if not points:
                    break

                for point in points:
                    route_id = point.payload.get(self.ROUTE_ID_KEY)
                    if route_id is not None:
                        route_ids.add(route_id)

                offset = next_offset
                if next_offset is None:
                    break

            logger.info(
                f"从Qdrant获取到 {len(route_ids)} 个现有路由ID: {sorted(route_ids)}"
            )
            return route_ids
        except Exception as e:
            logger.error(f"Failed to fetch existing route IDs: {e}", exc_info=True)
            raise

    def get_existing_route_hashes(self) -> Dict[int, str]:
        """获取Qdrant中所有现有的路由ID及其对应的哈希值

        Returns:
            {route_id: hash} 字典
        """
        try:
            route_hashes = {}
            offset = None
            batch_size = 100

            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=batch_size,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                points, next_offset = result
                if not points:
                    break

                for point in points:
                    payload = point.payload or {}
                    route_id = payload.get(self.ROUTE_ID_KEY)
                    route_hash = payload.get(self.ROUTE_HASH_KEY)
                    if route_id is not None and route_hash is not None:
                        # 如果同一个 ID 有多个点，哈希应该是一致的，这里直接覆盖
                        route_hashes[route_id] = route_hash

                offset = next_offset
                if next_offset is None:
                    break

            return route_hashes
        except Exception as e:
            logger.error(f"Failed to fetch existing route hashes: {e}", exc_info=True)
            return {}

    def get_collection_model_name(self) -> Optional[str]:
        """获取集合中存储的模型名称（通过检查第一个点的 payload）

        Returns:
            模型名称或 None
        """
        try:
            from qdrant_client.models import MatchValue

            result = self.client.scroll(
                collection_name=self.collection_name,
                limit=1,
                scroll_filter=Filter(
                    must_not=[
                        FieldCondition(
                            key=self.IS_ROUTE_METADATA_KEY,
                            match=MatchValue(value=True),
                        )
                    ]
                ),
                with_payload=True,
                with_vectors=False,
            )
            points, _ = result
            if points and points[0].payload:
                return points[0].payload.get(self.MODEL_NAME_KEY)
            return None
        except Exception:
            return None

    def scroll_all_points(
        self, with_vectors: bool = True, exclude_negative: bool = True
    ) -> List[Dict[str, Any]]:
        """遍历 collection 中所有点（用于可视化/诊断等离线分析场景）

        Args:
            with_vectors: 是否返回向量
            exclude_negative: 是否排除负例向量，默认为 True（诊断时应该排除负例）

        Returns:
            列表元素结构: {"id": str|int, "vector": [...](可选), "payload": {...}}
        """
        try:
            from qdrant_client.models import MatchValue

            results: List[Dict[str, Any]] = []
            offset = None
            batch_size = 200

            # Recovery-only metadata points must never enter diagnostics or tests.
            must_not = [
                FieldCondition(
                    key=self.IS_ROUTE_METADATA_KEY, match=MatchValue(value=True)
                )
            ]
            if exclude_negative:
                must_not.append(
                    FieldCondition(
                        key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                    )
                )
            scroll_filter = Filter(must_not=must_not)

            while True:
                scroll_params = {
                    "collection_name": self.collection_name,
                    "limit": batch_size,
                    "offset": offset,
                    "with_payload": True,
                    "with_vectors": with_vectors,
                }
                scroll_params["scroll_filter"] = scroll_filter

                points, next_offset = self.client.scroll(**scroll_params)

                for p in points:
                    # 双重检查：确保不是负例向量（如果 exclude_negative 为 True）
                    payload = p.payload or {}
                    if payload.get(self.IS_ROUTE_METADATA_KEY, False):
                        continue
                    if exclude_negative and payload.get(self.IS_NEGATIVE_KEY, False):
                        continue

                    item: Dict[str, Any] = {"id": p.id, "payload": payload}
                    if with_vectors:
                        item["vector"] = p.vector
                    results.append(item)

                if next_offset is None:
                    break
                offset = next_offset

            return results
        except Exception as e:
            logger.error(f"Failed to scroll all points: {e}", exc_info=True)
            raise

    def upsert_route_negative_samples(
        self,
        route_id: int,
        route_name: str,
        negative_samples: List[str],
        embeddings: List[List[float]],
        negative_threshold: float,
    ):
        """插入或更新路由的负例向量

        Args:
            route_id: 路由ID
            route_name: 路由名称
            negative_samples: 负例语句列表
            embeddings: 对应的向量列表
            negative_threshold: 负例相似度阈值
        """
        if len(negative_samples) != len(embeddings):
            raise ValueError("negative_samples和embeddings长度不匹配")

        points = []
        for negative_sample, embedding in zip(negative_samples, embeddings):
            # 使用确定性UUID生成point ID，添加negative前缀以区分
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_DNS,
                    f"negative:{route_id}:{route_name}:{negative_sample}",
                )
            )

            payload = {
                self.ROUTE_ID_KEY: route_id,
                self.ROUTE_NAME_KEY: route_name,
                self.UTTERANCE_KEY: negative_sample,
                self.IS_NEGATIVE_KEY: True,  # 标识为负例
                self.NEGATIVE_THRESHOLD_KEY: negative_threshold,
            }

            points.append(PointStruct(id=point_id, vector=embedding, payload=payload))

        try:
            self.client.upsert(collection_name=self.collection_name, points=points)
            logger.info(f"Updated route {route_name}: {len(points)} negative vectors")
        except Exception as e:
            logger.error(f"Failed to update negative points: {e}", exc_info=True)
            raise

    def search_negative_samples(
        self, query_vector: List[float], top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """搜索与查询向量最相似的负例向量

        Args:
            query_vector: 查询向量
            top_k: 返回Top K结果

        Returns:
            搜索结果列表，每个结果包含score和payload
        """
        try:
            from qdrant_client.models import MatchValue

            # 只搜索负例向量
            return self._search_grouped(
                query_vector=query_vector,
                top_k=top_k,
                query_filter=Filter(
                    must=[
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        )
                    ],
                    must_not=[
                        FieldCondition(
                            key=self.IS_ROUTE_METADATA_KEY,
                            match=MatchValue(value=True),
                        )
                    ],
                ),
            )
        except Exception as e:
            logger.error(f"Negative vector search failed: {e}", exc_info=True)
            raise

    def delete_route_negative_samples(self, route_id: int):
        """删除指定路由的所有负例向量点

        Args:
            route_id: 路由ID
        """
        try:
            from qdrant_client.models import MatchValue

            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key=self.ROUTE_ID_KEY, match=MatchValue(value=route_id)
                        ),
                        FieldCondition(
                            key=self.IS_NEGATIVE_KEY, match=MatchValue(value=True)
                        ),
                    ]
                ),
            )
            logger.info(f"Deleted all negative points for route ID {route_id}")
        except Exception as e:
            logger.error(f"Failed to delete negative points: {e}", exc_info=True)
            raise
