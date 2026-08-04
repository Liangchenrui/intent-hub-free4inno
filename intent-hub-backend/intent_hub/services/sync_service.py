"""同步服务 - 处理索引同步业务逻辑"""

from typing import Any, Dict

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.utils.logger import logger


class SyncService:
    """同步服务类 - 处理索引同步的核心业务逻辑"""

    def __init__(self, component_manager: ComponentManager):
        """初始化同步服务

        Args:
            component_manager: 组件管理器实例
        """
        self.component_manager = component_manager

    def reindex(self, force_full: bool = False) -> Dict[str, Any]:
        """重新索引：支持全量和增量两种模式

        Args:
            force_full: 如果为True，则执行全量重建（清空后重新创建）

        Returns:
            包含同步结果的字典
        """
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 1. 重新加载路由配置文件（热加载）
        route_manager.reload()

        # 2. 获取配置文件中的路由
        config_routes = route_manager.get_all_routes()
        config_route_ids = {route.id for route in config_routes}

        if force_full:
            return self._full_reindex(config_routes, encoder, qdrant_client, route_manager)
        else:
            return self._incremental_reindex(
                config_routes, config_route_ids, encoder, qdrant_client, route_manager
            )

    def _full_reindex(
        self, config_routes: list, encoder, qdrant_client, route_manager
    ) -> Dict[str, Any]:
        """全量重建模式：清空后重新创建"""
        logger.info("Running full reindex")
        qdrant_client.delete_all()

        total_points = 0
        total_negative_points = 0
        failed_routes = []
        for route in config_routes:
            try:
                # 处理正例向量
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold,
                    route_hash=route_manager.compute_route_hash(route),
                    model_name=Config.EMBEDDING_MODEL_NAME,
                )
                total_points += len(route.utterances)

                # 处理负例向量
                negative_samples = getattr(route, "negative_samples", [])
                if negative_samples:
                    negative_embeddings = encoder.encode(negative_samples)
                    negative_threshold = getattr(route, "negative_threshold", 0.95)
                    qdrant_client.upsert_route_negative_samples(
                        route_id=route.id,
                        route_name=route.name,
                        negative_samples=negative_samples,
                        embeddings=negative_embeddings,
                        negative_threshold=negative_threshold,
                    )
                    total_negative_points += len(negative_samples)
                else:
                    # 确保删除可能存在的旧负例向量
                    qdrant_client.delete_route_negative_samples(route.id)
                qdrant_client.upsert_route_metadata(
                    route=route,
                    route_hash=route_manager.compute_route_hash(route),
                    model_name=Config.EMBEDDING_MODEL_NAME,
                )
            except Exception as e:
                logger.error(
                    f"Failed processing route {route.name} (ID: {route.id}): {e}", exc_info=True
                )
                failed_routes.append(
                    {"route_id": route.id, "route_name": route.name, "error": str(e)}
                )

        # 全量同步后同步启动全量诊断，确保数据一致性
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService

            diag_service = DiagnosticService(self.component_manager)
            diag_service.analyze_all_overlaps(use_cache=False)
            logger.info("Full diagnostics completed after full sync")
        except Exception as e:
            logger.error(f"Failed to run full diagnostics after full sync: {e}")

        result = {
            "message": "Full reindex completed"
            if not failed_routes
            else f"Full reindex completed with {len(failed_routes)} route(s) failed",
            "mode": "full",
            "routes_count": len(config_routes),
            "total_points": total_points,
            "total_negative_points": total_negative_points,
            "success_count": len(config_routes) - len(failed_routes),
            "failed_count": len(failed_routes),
        }
        if failed_routes:
            result["failed_routes"] = failed_routes
            logger.warning(
                f"Full reindex completed with {len(failed_routes)} route(s) failed: {[r['route_name'] for r in failed_routes]}"
            )
        return result

    def _incremental_reindex(
        self,
        config_routes: list,
        config_route_ids: set,
        encoder,
        qdrant_client,
        route_manager,
    ) -> Dict[str, Any]:
        """增量更新模式：只更新变化的路由"""
        logger.info("Running incremental reindex")

        # 3. 获取 Qdrant 中现有的路由 ID 和哈希
        qdrant_route_hashes = qdrant_client.get_existing_route_hashes()
        existing_route_ids = set(qdrant_route_hashes.keys())

        # 4. 计算需要删除的路由（在 Qdrant 中存在但配置文件中不存在）
        routes_to_delete = existing_route_ids - config_route_ids
        deleted_count = 0
        for route_id in routes_to_delete:
            logger.info(f"Deleting removed route: {route_id}")
            qdrant_client.delete_route(route_id)
            qdrant_client.delete_route_negative_samples(route_id)
            deleted_count += 1

        # 5. 增量更新配置文件中的路由
        updated_count = 0
        skipped_count = 0
        new_count = 0
        total_points = 0

        for route in config_routes:
            local_hash = route_manager.compute_route_hash(route)
            qdrant_hash = qdrant_route_hashes.get(route.id)
            
            is_new_route = route.id not in existing_route_ids
            needs_update = not is_new_route and local_hash != qdrant_hash

            if is_new_route or needs_update:
                if is_new_route:
                    logger.info(f"New route: {route.name} (ID: {route.id})")
                    new_count += 1
                else:
                    logger.info(f"Updating route (hash changed): {route.name} (ID: {route.id})")
                    # 先删除旧的向量点（包括正例和负例）
                    qdrant_client.delete_route(route.id)
                    qdrant_client.delete_route_negative_samples(route.id)
                    updated_count += 1

                # 处理正例向量
                embeddings = encoder.encode(route.utterances)
                qdrant_client.upsert_route_utterances(
                    route_id=route.id,
                    route_name=route.name,
                    utterances=route.utterances,
                    embeddings=embeddings,
                    score_threshold=route.score_threshold,
                    route_hash=local_hash,
                    model_name=Config.EMBEDDING_MODEL_NAME,
                )
                total_points += len(route.utterances)

                # 处理负例向量
                negative_samples = getattr(route, "negative_samples", [])
                if negative_samples:
                    negative_embeddings = encoder.encode(negative_samples)
                    negative_threshold = getattr(route, "negative_threshold", 0.95)
                    qdrant_client.upsert_route_negative_samples(
                        route_id=route.id,
                        route_name=route.name,
                        negative_samples=negative_samples,
                        embeddings=negative_embeddings,
                        negative_threshold=negative_threshold,
                    )
            else:
                skipped_count += 1

            # Always backfill the complete recovery record, including for unchanged
            # legacy routes that predate metadata points.
            qdrant_client.upsert_route_metadata(
                route=route,
                route_hash=local_hash,
                model_name=Config.EMBEDDING_MODEL_NAME,
            )

        # 处理被删除的路由缓存清理
        if routes_to_delete:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                for rid in routes_to_delete:
                    diag_service.remove_route_from_cache(rid)
            except Exception as e:
                logger.error(f"Failed to clear diagnostic cache for deleted routes: {e}")

        # 增量同步后，如果有任何变化，同步启动全量诊断确保最新
        if new_count > 0 or updated_count > 0 or deleted_count > 0:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                diag_service.analyze_all_overlaps(use_cache=False)
                logger.info("Full diagnostics completed after incremental sync")
            except Exception as e:
                logger.error(f"Failed to run full diagnostics after incremental sync: {e}")

        return {
            "message": "Incremental reindex completed",
            "mode": "incremental",
            "routes_count": len(config_routes),
            "new_routes": new_count,
            "updated_routes": updated_count,
            "deleted_routes": deleted_count,
            "skipped_routes": skipped_count,
            "total_points": total_points,
        }

    def sync_route(self, route_id: int) -> Dict[str, Any]:
        """同步单个路由到向量数据库

        Args:
            route_id: 要同步的路由ID

        Returns:
            包含同步结果的字典

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()

        encoder = self.component_manager.encoder
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 重新加载路由配置文件（热加载）
        route_manager.reload()

        # 获取路由配置
        route = route_manager.get_route(route_id)
        if not route:
            raise ValueError(f"Route ID {route_id} not found")

        logger.info(f"Syncing route: {route.name} (ID: {route_id})")

        # 先删除旧的向量点（包括正例和负例）
        qdrant_client.delete_route(route_id)
        qdrant_client.delete_route_negative_samples(route_id)

        # 重新编码并插入新的正例向量点
        embeddings = encoder.encode(route.utterances)
        qdrant_client.upsert_route_utterances(
            route_id=route.id,
            route_name=route.name,
            utterances=route.utterances,
            embeddings=embeddings,
            score_threshold=route.score_threshold,
            route_hash=route_manager.compute_route_hash(route),
            model_name=Config.EMBEDDING_MODEL_NAME,
        )
        total_points = len(route.utterances)

        # 处理负例向量
        negative_samples = getattr(route, "negative_samples", [])
        total_negative_points = 0
        if negative_samples:
            negative_embeddings = encoder.encode(negative_samples)
            negative_threshold = getattr(route, "negative_threshold", 0.95)
            qdrant_client.upsert_route_negative_samples(
                route_id=route.id,
                route_name=route.name,
                negative_samples=negative_samples,
                embeddings=negative_embeddings,
                negative_threshold=negative_threshold,
            )
            total_negative_points = len(negative_samples)

        qdrant_client.upsert_route_metadata(
            route=route,
            route_hash=route_manager.compute_route_hash(route),
            model_name=Config.EMBEDDING_MODEL_NAME,
        )

        logger.info(
            f"Synced route {route.name} (ID: {route_id}): {total_points} positive, {total_negative_points} negative vectors"
        )

        return {
            "message": f"Route {route.name} synced",
            "route_id": route_id,
            "route_name": route.name,
            "total_points": total_points,
            "total_negative_points": total_negative_points,
        }

    def sync_routes(self, route_ids: list) -> Dict[str, Any]:
        """同步多个路由到向量数据库

        Args:
            route_ids: 要同步的路由ID列表

        Returns:
            包含同步结果的字典
        """
        self.component_manager.ensure_ready()

        results = []
        for route_id in route_ids:
            try:
                result = self.sync_route(route_id)
                results.append(result)
            except Exception as e:
                logger.error(f"Sync route {route_id} failed: {e}")
                results.append({"route_id": route_id, "error": str(e)})

        return {
            "message": f"Synced {len([r for r in results if 'error' not in r])} route(s)",
            "results": results,
        }
