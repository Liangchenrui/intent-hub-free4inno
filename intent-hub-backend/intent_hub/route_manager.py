"""Route-shaped adapter over the shared SQLite repository."""
import hashlib
import json
import os
import re
from pathlib import Path
from threading import RLock
from typing import List, Dict, Optional
from intent_hub.config import Config
from intent_hub.models import RouteConfig
from intent_hub.repository import Repository
from intent_hub.utils.logger import logger

class RouteManager:
    def __init__(self, config_path=None):
        path = Path(config_path or Config.ROUTES_CONFIG_PATH)
        if not path.is_absolute():
            path = Path(__file__).parent / path
        self.config_path = str(path)
        self.repository = Repository(path if path.suffix in {'.db', '.sqlite', '.sqlite3'} else path.with_suffix('.sqlite3'))
        self._lock = self.repository._lock
        # Legacy JSON is read only once. It is never rewritten or used as a second store.
        if path.suffix == '.json' and path.exists() and not self.repository.metadata('legacy_imported'):
            if self.repository.all():
                raise ValueError('Existing database requires explicit migration')
            raw = json.loads(path.read_text(encoding='utf-8'))
            raw, _ = self._migrate_route_keys(raw)
            routes = [RouteConfig(**item) for item in raw]
            if len({r.id for r in routes}) != len(routes):
                raise ValueError('Duplicate entity IDs')
            with self.repository.transaction() as db:
                for route in routes:
                    self.repository.save(route, db, enqueue=False)
                db.execute("INSERT INTO metadata VALUES ('legacy_imported','1')")

    def get_route(self, route_id):
        return self.repository.get(route_id)

    def get_all_routes(self):
        return self.repository.all()

    def replace_routes(self, routes):
        if len({r.id for r in routes}) != len(routes) or len({r.route_key for r in routes}) != len(routes):
            raise ValueError('Duplicate route ID or route_key')
        with self.repository.transaction() as db:
            ids = {r.id for r in routes}
            for row in db.execute('SELECT id FROM entities').fetchall():
                if row[0] not in ids:
                    self.repository.delete(row[0], db)
            for route in routes:
                self.repository.save(route, db)

    def get_route_by_key(self, route_key):
        return next((r for r in self.get_all_routes() if r.route_key == route_key), None)

    def is_route_key_unique(self, route_key, exclude_route_id=None):
        return not any(r.route_key == route_key and r.id != exclude_route_id for r in self.get_all_routes())

    def search_routes(self, query):
        q = query.lower()
        return [r for r in self.get_all_routes() if not q or any(q in s.lower() for s in [r.name, r.description, *r.utterances])]

    def add_route(self, route):
        route.route_key = self.normalize_route_key(route.route_key)
        if not route.route_key:
            raise ValueError('route_key is required')
        if not self.is_route_key_unique(route.route_key, route.id):
            raise ValueError(f"route_key '{route.route_key}' already exists")
        self.repository.save(route)
        return True

    def update_route(self, route_id, route):
        if self.get_route(route_id) is None:
            return False
        route.id = route_id
        return self.add_route(route)

    def delete_route(self, route_id):
        return self.repository.delete(route_id)

    def allocate_route_id(self):
        return self.repository.allocate()

    def update_sync_state(self, route_id, **changes):
        with self.repository.transaction() as db:
            row = db.execute('SELECT body FROM entities WHERE id=?', (route_id,)).fetchone()
            if not row:
                return None
            route = RouteConfig.model_validate_json(row[0])
            route.sync = route.sync or RouteConfig.RouteSync()
            expected = changes.pop('expected_version', None)
            if expected is not None and route.sync.version != expected:
                return None
            for key, value in changes.items():
                if hasattr(route.sync, key):
                    setattr(route.sync, key, value)
            self.repository.save(route, db, enqueue=False)
            return route

    def get_score_threshold(self, route_id):
        route = self.get_route(route_id)
        return route.score_threshold if route else None

    def reload(self):
        pass  # Every read already observes SQLite's committed state.

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
            "lifecycle_status": getattr(route, "lifecycle_status", "active"),
            "embedding_model": Config.EMBEDDING_MODEL_NAME,
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
                route.id: self.compute_route_hash(route)
                for route in self.get_all_routes()
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
