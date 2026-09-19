"""同步服务 - 处理索引同步业务逻辑"""

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Dict

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.intent_description import description_text
from intent_hub.models import RouteConfig
from intent_hub.utils.logger import logger


class SyncService:
    """同步服务类 - 处理索引同步的核心业务逻辑"""

    execution_lock = Config.LOCK

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
        config_routes = [route.model_copy(deep=True) for route in route_manager.get_all_routes() if route.lifecycle_status == "active"]
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
                self._sync_metadata(route)
            except Exception as e:
                logger.error(
                    f"Failed processing route {route.name} (ID: {route.id}): {e}", exc_info=True
                )
                failed_routes.append(
                    {"route_id": route.id, "route_name": route.name, "error": str(e)}
                )

        self._validate_index(config_routes, qdrant_client, route_manager)

        # Diagnostics is a separate background phase and never delays index readiness.
        try:
            from intent_hub.services.diagnostic_service import DiagnosticService

            diag_service = DiagnosticService(self.component_manager)
            diag_service.run_async_diagnostics("full")
            logger.info("Full diagnostics scheduled after full sync")
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
        initial = qdrant_client.fast_index_summary()
        existing_route_ids = set(initial['route_ids'])

        # 4. 计算需要删除的路由（在 Qdrant 中存在但配置文件中不存在）
        routes_to_delete = existing_route_ids - config_route_ids
        self._guard_mass_deletion(len(existing_route_ids), len(routes_to_delete))
        deleted_count = 0
        for route_id in routes_to_delete:
            logger.info(f"Deleting removed route: {route_id}")
            qdrant_client.delete_route(route_id)
            deleted_count += 1

        # 5. 增量更新配置文件中的路由
        updated_count = 0
        skipped_count = 0
        new_count = 0
        total_points = 0

        records = initial['metadata']
        route_results = []
        for route in config_routes:
            metadata = records.get(route.id, {})
            if not initial['manifests_valid']:
                metadata = {**metadata, 'sync_schema': 0} if metadata else {}
            result = self._sync_delta(route, metadata)
            route_results.append(result)
            if route.id not in existing_route_ids:
                new_count += 1
            elif result["changed"]:
                updated_count += 1
            else:
                skipped_count += 1
            total_points += result["total_points"]

        self._validate_index(config_routes, qdrant_client, route_manager, fast=True,
                             actual=initial if not (new_count or updated_count or deleted_count) else None)

        # 处理被删除的路由缓存清理
        if routes_to_delete:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                for rid in routes_to_delete:
                    diag_service.remove_route_from_cache(rid)
            except Exception as e:
                logger.error(f"Failed to clear diagnostic cache for deleted routes: {e}")

        # Refresh diagnostics asynchronously after index writes are complete.
        if new_count > 0 or updated_count > 0 or deleted_count > 0:
            try:
                from intent_hub.services.diagnostic_service import DiagnosticService

                diag_service = DiagnosticService(self.component_manager)
                diag_service.run_async_diagnostics("full")
                logger.info("Full diagnostics scheduled after incremental sync")
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
            "encoded_texts": sum(r['encoded_texts'] for r in route_results),
            "route_results": route_results,
        }

    @staticmethod
    def _guard_mass_deletion(previous_count: int, deleted_count: int) -> None:
        if previous_count and deleted_count / previous_count > Config.MAX_DELETE_RATIO:
            raise ValueError(
                f"本次将删除 {deleted_count}/{previous_count} 个路由，超过安全阈值；"
                "请确认配置后使用全量重建"
            )

    @staticmethod
    def _validate_index(config_routes: list, qdrant_client, route_manager, fast=False, actual=None) -> None:
        expected_hashes = {
            route.id: route_manager.compute_route_hash(route) for route in config_routes
        }
        expected_points = sum(
            len(set(route.utterances)) + len(set(getattr(route, "negative_samples", []))) + 1
            for route in config_routes
        )
        if actual is None:
            actual = qdrant_client.fast_index_summary() if fast else qdrant_client.index_summary()
        if (
            actual["points_count"] != expected_points
            or actual["route_ids"] != sorted(expected_hashes)
            or actual["route_hashes"] != expected_hashes
        ):
            raise RuntimeError(
                "Qdrant 索引校验失败："
                f"期望 {expected_points} 个点和 {len(expected_hashes)} 个路由，"
                f"实际 {actual['points_count']} 个点和 {len(actual['route_ids'])} 个路由"
            )

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
        route = route.model_copy(deep=True)

        if route.lifecycle_status != "active":
            qdrant_client.delete_route(route_id)
            self._mark_synced_if_current(route.id, route.sync.version if route.sync else 0)
            return {"route_id": route.id, "total_points": 0, "total_negative_points": 0,
                    "changed": True, "metadata_committed": True}
        return self._sync_delta(route)

    def _sync_delta(self, route, metadata=None):
        from intent_hub.services.delta_sync import sync_delta

        result = sync_delta(self, route, metadata)
        logger.info("Route sync id=%s changed=%s encoded=%s timings_ms=%s",
                    route.id, result["changed"], result["encoded_texts"], result["timings_ms"])
        return result

    def _sync_metadata(self, route: RouteConfig) -> None:
        """Backfill legacy vectors and acknowledge sync only after the final write."""
        route = route.model_copy(deep=True)
        manager = self.component_manager
        embedding = manager.qdrant_client.get_description_embedding(route, Config.EMBEDDING_MODEL_NAME)
        if embedding is None:
            embedding = manager.encoder.encode_single(description_text(route))
        snapshot = route.model_copy(deep=True)
        snapshot.sync = snapshot.sync or RouteConfig.RouteSync()
        expected_version = snapshot.sync.version
        snapshot.sync.status = "synced"
        snapshot.sync.synced_version = expected_version
        snapshot.sync.last_synced_at = datetime.now(timezone.utc).isoformat()
        snapshot.sync.error = None
        manager.qdrant_client.upsert_route_metadata(
            route=snapshot,
            route_hash=manager.route_manager.compute_route_hash(route),
            model_name=Config.EMBEDDING_MODEL_NAME,
            embedding=embedding,
        )
        if (
            route.sync is None
            or route.sync.status != "synced"
            or route.sync.synced_version != expected_version
        ):
            self._mark_synced_if_current(route.id, expected_version)

    def _mark_synced_if_current(self, route_id: int, expected_version: int):
        """Only acknowledge the exact route version that was just indexed."""
        route_manager = self.component_manager.route_manager
        current = route_manager.get_route(route_id)
        if current is None:
            return None
        current_version = current.sync.version if current.sync else 0
        if current_version != expected_version:
            logger.info(
                "Route %s advanced from version %s to %s during sync; leaving it pending",
                route_id,
                expected_version,
                current_version,
            )
            return None
        return route_manager.update_sync_state(
            route_id,
            **({"expected_version": expected_version} if hasattr(route_manager, "repository") else {}),
            status="synced",
            synced_version=expected_version,
            last_synced_at=datetime.now(timezone.utc).isoformat(),
            error=None,
        )

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
