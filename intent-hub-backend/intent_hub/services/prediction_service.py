"""预测服务 - 处理路由预测业务逻辑"""

from typing import Dict, List

from intent_hub.utils.logger import logger

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.models import PredictRequest, PredictResponse


class PredictionService:
    """预测服务类 - 处理路由预测的核心业务逻辑"""

    def __init__(self, component_manager: ComponentManager):
        """初始化预测服务

        Args:
            component_manager: 组件管理器实例
        """
        self.component_manager = component_manager

    def predict(self, request: PredictRequest) -> List[PredictResponse]:
        """执行路由预测，返回所有匹配的路由列表

        Args:
            request: 预测请求

        Returns:
            预测响应列表，包含所有相似度大于设定阈值的路由，按分数降序排列
        """
        # 确保组件已就绪
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager
        route_manager.reload()
        result_limit = max(1, len(route_manager.get_all_routes()))

        # 1. 向量化
        query_vector = encoder.encode_single(request.text)
        logger.debug(f"Query text: {request.text}, vector dim: {len(query_vector)}")

        # 2. 负例检查：先检查查询是否与任何负例向量过于接近
        excluded_route_ids = set()
        negative_search_results = qdrant_client.search_negative_samples(
            query_vector, top_k=result_limit
        )

        for neg_result in negative_search_results:
            score = neg_result["score"]
            payload = neg_result["payload"]
            route_id = payload[qdrant_client.ROUTE_ID_KEY]
            negative_threshold = payload.get(
                qdrant_client.NEGATIVE_THRESHOLD_KEY, 0.95  # 默认负例阈值
            )

            # 如果查询与负例向量相似度超过阈值，排除该路由
            if score >= negative_threshold:
                excluded_route_ids.add(route_id)
                logger.info(
                    f"Negative excluded: route_id={route_id}, "
                    f"negative_score={score:.4f} >= negative_threshold={negative_threshold}, "
                    f"negative_sample={payload.get(qdrant_client.UTTERANCE_KEY)}"
                )

        # 3. 相似度检索 (获取较多的候选结果以便过滤)
        search_results = qdrant_client.search(query_vector, top_k=result_limit)
        logger.debug(f"Search raw result count: {len(search_results)}")

        if not search_results:
            # 没有找到任何结果，返回默认路由
            logger.warning(
                f"Search returned no results, using default route. Query: {request.text}"
            )
            return [
                PredictResponse(
                    id=Config.DEFAULT_ROUTE_ID,
                    name=Config.DEFAULT_ROUTE_NAME,
                    route_key=Config.DEFAULT_ROUTE_KEY,
                    score=None,
                )
            ]

        # 4. 按路由ID分组并进行阈值过滤（同时排除负例匹配的路由）
        # 因为 Qdrant 返回的是 utterance 级别的匹配，一个路由可能有多个匹配项，取最高分
        matched_routes: Dict[int, PredictResponse] = {}

        for result in search_results:
            score = result["score"]
            payload = result["payload"]
            route_id = payload[qdrant_client.ROUTE_ID_KEY]
            route_name = payload[qdrant_client.ROUTE_NAME_KEY]
            route = route_manager.get_route(route_id)
            route_key = route.route_key if route else f"route.{route_id}"
            route_name = route.name if route else route_name

            # 跳过被负例排除的路由
            if route_id in excluded_route_ids:
                logger.debug(
                    f"Skipping negative-excluded route: route_id={route_id}, score={score:.4f}"
                )
                continue

            # 获取该路由的阈值
            threshold = route_manager.get_score_threshold(route_id)
            if threshold is None:
                threshold = payload.get(qdrant_client.SCORE_THRESHOLD_KEY, 0.75)

            # 阈值校验
            if score >= threshold:
                # 如果该路由已在匹配列表中，只保留最高分
                if (
                    route_id not in matched_routes
                    or score > matched_routes[route_id].score
                ):
                    matched_routes[route_id] = PredictResponse(
                        id=route_id,
                        name=route_name,
                        route_key=route_key,
                        score=float(score),
                    )
                    logger.debug(
                        f"Match: route_id={route_id}, score={score:.4f} >= threshold={threshold}"
                    )
            else:
                logger.debug(
                    f"Below threshold: route_id={route_id}, score={score:.4f} < threshold={threshold}"
                )

        # 5. 排序并转换结果
        sorted_results = sorted(
            matched_routes.values(),
            key=lambda x: x.score if x.score is not None else 0,
            reverse=True,
        )

        if not sorted_results:
            # 如果没有路由满足阈值，返回默认路由
            logger.info(f"No route above threshold, using default route. Query: {request.text}")
            return [
                PredictResponse(
                    id=Config.DEFAULT_ROUTE_ID,
                    name=Config.DEFAULT_ROUTE_NAME,
                    route_key=Config.DEFAULT_ROUTE_KEY,
                    score=None,
                )
            ]

        logger.info(f"Matched route count: {len(sorted_results)}")
        return sorted_results
