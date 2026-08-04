"""路由管理器 - 负责内存缓存和热加载"""

import hashlib
import json
import os
import re
from pathlib import Path
from threading import RLock
from typing import Dict, List, Optional

from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.utils.logger import logger


class RouteManager:
    """路由管理器，维护内存缓存和热加载机制"""

    def __init__(self, config_path: Optional[str] = None):
        """初始化路由管理器

        Args:
            config_path: 路由配置文件路径（绝对路径或相对于intent_hub包目录的路径）
        """
        if config_path:
            raw_path = config_path
        else:
            raw_path = Config.ROUTES_CONFIG_PATH

        current_file = Path(__file__).resolve()
        intent_hub_dir = current_file.parent

        if os.path.isabs(raw_path):
            self.config_path = raw_path
        else:
            self.config_path = str(intent_hub_dir / raw_path)

        self._routes_cache: Dict[int, RouteConfig] = {}
        self._lock = RLock()

        logger.info(f"Routes config path: {self.config_path}")

        config_dir = os.path.dirname(self.config_path)
        if config_dir:  # 如果路径包含目录
            os.makedirs(config_dir, exist_ok=True)

        self._load_from_file()

    def _load_from_file(self):
        """从文件加载路由配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    routes_data = json.load(f)
                    logger.debug(f"Parsed {len(routes_data)} route entries from JSON")
                    routes_data, migrated = self._migrate_route_keys(routes_data)
                    routes = [RouteConfig(**route) for route in routes_data]
                    self._routes_cache = {route.id: route for route in routes}
                logger.info(
                    f"Loaded {len(self._routes_cache)} routes from file: {[r.name for r in routes]}"
                )
                if migrated:
                    self._save_to_file()
                    logger.info("Persisted migrated route_key values to routes config")
            except Exception as e:
                logger.error(f"Failed to load routes config: {e}", exc_info=True)
                logger.error(f"Config path: {self.config_path}")
                self._routes_cache = {}
        else:
            logger.warning(
                f"Routes config file not found, initializing empty: {self.config_path}"
            )
            self._routes_cache = {}
            try:
                # 自动创建一个空的配置文件
                self._save_to_file()
            except Exception as e:
                logger.error(f"Failed to create empty routes config: {e}")

    def _save_to_file(self):
        """保存路由配置到文件"""
        try:
            routes_data = [
                route.model_dump()
                if hasattr(route, "model_dump")
                else route.dict()
                for route in self._routes_cache.values()
            ]
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(routes_data, f, ensure_ascii=False, indent=2)
            logger.info(f"Routes config saved: {self.config_path}")
        except Exception as e:
            logger.error(f"Failed to save routes config: {e}", exc_info=True)
            raise

    def get_route(self, route_id: int) -> Optional[RouteConfig]:
        """获取路由配置

        Args:
            route_id: 路由ID

        Returns:
            路由配置，不存在返回None
        """
        with self._lock:
            return self._routes_cache.get(route_id)

    def get_all_routes(self) -> List[RouteConfig]:
        """获取所有路由配置

        Returns:
            路由配置列表
        """
        with self._lock:
            return list(self._routes_cache.values())

    def replace_routes(self, routes: List[RouteConfig]) -> None:
        """Atomically replace the local route list and persist it once."""
        with self._lock:
            self._routes_cache = {route.id: route for route in routes}
            self._save_to_file()
            logger.info(f"Replaced local routes: {len(routes)} routes")

    def get_route_by_key(self, route_key: str) -> Optional[RouteConfig]:
        """按业务路由标识获取路由配置"""
        with self._lock:
            for route in self._routes_cache.values():
                if route.route_key == route_key:
                    return route
        return None

    def is_route_key_unique(
        self, route_key: str, exclude_route_id: Optional[int] = None
    ) -> bool:
        """检查 route_key 是否唯一"""
        with self._lock:
            for route in self._routes_cache.values():
                if exclude_route_id is not None and route.id == exclude_route_id:
                    continue
                if route.route_key == route_key:
                    return False
        return True

    def search_routes(self, query: str) -> List[RouteConfig]:
        """通过名称、描述或例句搜索路由

        Args:
            query: 搜索关键词

        Returns:
            匹配的路由配置列表
        """
        if not query:
            return self.get_all_routes()

        query = query.lower()
        results = []

        with self._lock:
            for route in self._routes_cache.values():
                # 检查名称
                if route.name and query in route.name.lower():
                    results.append(route)
                    continue

                # 检查描述
                if route.description and query in route.description.lower():
                    results.append(route)
                    continue

                # 检查例句
                if route.utterances:
                    if any(query in utt.lower() for utt in route.utterances):
                        results.append(route)
                        continue

        return results

    def add_route(self, route: RouteConfig) -> bool:
        """添加路由配置

        Args:
            route: 路由配置

        Returns:
            是否成功添加
        """
        with self._lock:
            route.route_key = self.normalize_route_key(route.route_key)
            if not route.route_key:
                raise ValueError("route_key is required")
            if not self.is_route_key_unique(route.route_key, exclude_route_id=route.id):
                raise ValueError(f"route_key '{route.route_key}' already exists")
            if route.id in self._routes_cache:
                logger.warning(f"Route ID {route.id} already exists, updating")
            self._routes_cache[route.id] = route
            self._save_to_file()
            logger.info(f"Route added/updated: {route.name} (ID: {route.id})")
            return True

    def update_route(self, route_id: int, route: RouteConfig) -> bool:
        """更新路由配置

        Args:
            route_id: 路由ID
            route: 新的路由配置

        Returns:
            是否成功更新
        """
        with self._lock:
            if route_id not in self._routes_cache:
                logger.warning(f"Route ID {route_id} not found")
                return False

            # 确保ID一致
            route.route_key = self.normalize_route_key(route.route_key)
            if not route.route_key:
                raise ValueError("route_key is required")
            if not self.is_route_key_unique(route.route_key, exclude_route_id=route_id):
                raise ValueError(f"route_key '{route.route_key}' already exists")
            route.id = route_id
            self._routes_cache[route_id] = route
            self._save_to_file()
            logger.info(f"Route updated: {route.name} (ID: {route_id})")
            return True

    def delete_route(self, route_id: int) -> bool:
        """删除路由配置，并重排ID保证连续

        Args:
            route_id: 路由ID

        Returns:
            是否成功删除
        """
        with self._lock:
            if route_id not in self._routes_cache:
                logger.warning(f"Route ID {route_id} not found")
                return False

            route_name = self._routes_cache[route_id].name
            del self._routes_cache[route_id]

            # 重排ID：保证序号连续从1开始
            sorted_routes = sorted(self._routes_cache.values(), key=lambda x: x.id)
            new_cache = {}
            for i, route in enumerate(sorted_routes, 1):
                route.id = i
                new_cache[i] = route
            self._routes_cache = new_cache

            self._save_to_file()
            logger.info(f"Route deleted: {route_name} (ID: {route_id}), IDs reordered")
            return True

    def get_score_threshold(self, route_id: int) -> Optional[float]:
        """获取路由的相似度阈值

        Args:
            route_id: 路由ID

        Returns:
            相似度阈值，不存在返回None
        """
        route = self.get_route(route_id)
        return route.score_threshold if route else None

    def reload(self):
        """重新加载配置文件（热加载）"""
        logger.info("Hot reload: reloading routes config")
        with self._lock:
            old_count = len(self._routes_cache)
            self._load_from_file()
            new_count = len(self._routes_cache)
            logger.info(f"Hot reload done: {old_count} -> {new_count} routes")

    @staticmethod
    def compute_route_hash(route: RouteConfig) -> str:
        """计算路由配置的哈希值，用于检测路由是否发生变化

        Args:
            route: 路由配置

        Returns:
            路由配置的MD5哈希值（十六进制字符串）
        """
        route_data = {
            "id": route.id,
            "name": route.name,
            "route_key": route.route_key,
            "description": route.description,
            "utterances": sorted(route.utterances),  # 排序以确保一致性
            "negative_samples": sorted(getattr(route, "negative_samples", [])),
            "score_threshold": route.score_threshold,
            "negative_threshold": getattr(route, "negative_threshold", 0.95),
            "source": (
                route.source.model_dump()
                if getattr(route, "source", None) is not None
                else None
            ),
            "sync": (
                route.sync.model_dump()
                if getattr(route, "sync", None) is not None
                else None
            ),
            "lifecycle_status": getattr(route, "lifecycle_status", "active"),
        }
        route_json = json.dumps(route_data, ensure_ascii=False, sort_keys=True)
        return hashlib.md5(route_json.encode("utf-8")).hexdigest()

    def get_route_hash(self, route_id: int) -> Optional[str]:
        """获取指定路由的哈希值

        Args:
            route_id: 路由ID

        Returns:
            路由哈希值，不存在返回None
        """
        route = self.get_route(route_id)
        return self.compute_route_hash(route) if route else None

    def get_all_route_hashes(self) -> Dict[int, str]:
        """获取所有路由的哈希值字典

        Returns:
            {route_id: hash} 字典
        """
        with self._lock:
            return {
                route_id: self.compute_route_hash(route)
                for route_id, route in self._routes_cache.items()
            }

    @staticmethod
    def normalize_route_key(raw_value: str) -> str:
        """标准化 route_key，保持规则宽松但去除明显无效字符"""
        normalized = raw_value.strip().lower()
        normalized = re.sub(r"\s+", ".", normalized)
        normalized = re.sub(r"\.{2,}", ".", normalized)
        return normalized.strip(".")

    def _migrate_route_keys(self, routes_data: List[dict]) -> tuple[List[dict], bool]:
        """为旧数据补齐 route_key，并在必要时修复空值或重复值"""
        migrated = False
        used_keys = set()

        for route in routes_data:
            current_key = str(route.get("route_key", "") or "")
            normalized_key = self.normalize_route_key(current_key)

            if not normalized_key:
                normalized_key = self._build_route_key_candidate(
                    route.get("name", ""), route.get("id", 0), used_keys
                )
                migrated = True
                logger.warning(
                    f"Route ID {route.get('id')} missing route_key, generated '{normalized_key}'"
                )
            elif normalized_key != current_key:
                migrated = True

            unique_key = self._dedupe_route_key(
                normalized_key, route.get("id", 0), used_keys
            )
            if unique_key != normalized_key:
                migrated = True
                logger.warning(
                    f"Route ID {route.get('id')} route_key duplicated, adjusted to '{unique_key}'"
                )

            route["route_key"] = unique_key
            used_keys.add(unique_key)

        return routes_data, migrated

    def _build_route_key_candidate(
        self, route_name: str, route_id: int, used_keys: set[str]
    ) -> str:
        """基于路由名称生成一个宽松可用的 route_key 候选值"""
        normalized_name = self.normalize_route_key(route_name)
        base_key = normalized_name or f"route.{route_id or len(used_keys) + 1}"
        return self._dedupe_route_key(base_key, route_id, used_keys)

    @staticmethod
    def _dedupe_route_key(base_key: str, route_id: int, used_keys: set[str]) -> str:
        """为 route_key 追加后缀以保证唯一性"""
        candidate = base_key
        suffix = route_id or 1

        while candidate in used_keys:
            candidate = f"{base_key}.{suffix}"
            suffix += 1

        return candidate
