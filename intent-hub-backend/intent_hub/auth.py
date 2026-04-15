"""认证模块 - 管理API Key的生成、验证和存储"""

import time
import uuid
from functools import wraps
from typing import Any, Dict, Optional, Set

from flask import g, jsonify, request
from intent_hub.utils.logger import logger

from intent_hub.models import ErrorResponse
from intent_hub.services.tenant_auth_service import TenantAuthService


class AuthManager:
    """API Key认证管理器（内存存储，支持TTL和用户key管理）"""

    KEY_TTL: int = 30 * 60

    def __init__(self):
        self._user_keys: Dict[str, Dict[str, Any]] = {}
        self._key_to_user: Dict[str, str] = {}
        self._load_initial_keys()
        self.cleanup_expired_keys()

    def verify_user(self, username: str, password: str) -> bool:
        """验证用户名和密码

        Args:
            username: 用户名
            password: 密码

        Returns:
            bool: 验证是否通过
        """
        from intent_hub.config import Config

        return (
            username == Config.DEFAULT_USERNAME and password == Config.DEFAULT_PASSWORD
        )

    def _load_initial_keys(self):
        """从配置加载初始API keys"""
        from intent_hub.config import Config

        if hasattr(Config, "API_KEYS") and Config.API_KEYS:
            config_keys = [k.strip() for k in Config.API_KEYS.split(",") if k.strip()]
            for key in config_keys:
                self._key_to_user[key] = "__legacy__"
            logger.info(
                f"Loaded {len(config_keys)} API keys from config (legacy mode, no TTL)"
            )

    def generate_key(self, username: str) -> str:
        """为指定用户生成或获取API key

        Args:
            username: 用户名

        Returns:
            str: API key（如果用户已有未过期的key，则返回该key；否则生成新的）
        """
        self.cleanup_expired_keys()

        if username in self._user_keys:
            user_key_info = self._user_keys[username]
            key = user_key_info["key"]
            created_at = user_key_info["created_at"]

            # 检查key是否过期
            if time.time() - created_at < self.KEY_TTL:
                logger.info(f"User {username} using existing API key: {key[:8]}...")
                return key
            else:
                logger.info(f"User {username} API key expired, generating new key")
                old_key = key
                if old_key in self._key_to_user:
                    del self._key_to_user[old_key]

        new_key = str(uuid.uuid4())
        current_time = time.time()

        self._user_keys[username] = {"key": new_key, "created_at": current_time}
        self._key_to_user[new_key] = username

        logger.info(f"Generated new API key for user {username}: {new_key[:8]}...")
        return new_key

    def add_key(self, key: str) -> bool:
        """添加一个API key（兼容方法，用于兼容旧配置）"""
        if not key or not key.strip():
            return False
        key = key.strip()
        # 添加到兼容映射中（无TTL限制）
        self._key_to_user[key] = "__legacy__"
        logger.info(f"Added API key: {key[:8]}... (legacy mode, no TTL)")
        return True

    def remove_key(self, key: str) -> bool:
        """移除一个API key"""
        key = key.strip() if key else ""
        if not key:
            return False

        if key in self._key_to_user:
            username = self._key_to_user[key]
            # 如果是用户关联的key，也要从用户映射中删除
            if username != "__legacy__" and username in self._user_keys:
                if self._user_keys[username].get("key") == key:
                    del self._user_keys[username]
            del self._key_to_user[key]
            logger.info(f"Removed API key: {key[:8]}...")
            return True
        return False

    def is_valid(self, key: str) -> bool:
        """验证API key是否有效（检查TTL）"""
        if not key:
            return False

        key = key.strip()

        # 检查是否是兼容模式的key（无TTL限制）
        if key in self._key_to_user and self._key_to_user[key] == "__legacy__":
            return True

        # 检查是否是用户关联的key
        if key in self._key_to_user:
            username = self._key_to_user[key]
            if username in self._user_keys:
                user_key_info = self._user_keys[username]
                created_at = user_key_info["created_at"]

                # 检查是否过期
                if time.time() - created_at < self.KEY_TTL:
                    return True
                else:
                    self.cleanup_expired_keys()
                    return False

        return False

    def cleanup_expired_keys(self) -> int:
        """清理所有过期的key

        Returns:
            int: 清理的key数量
        """
        current_time = time.time()
        expired_users = []

        for username, key_info in self._user_keys.items():
            created_at = key_info["created_at"]
            if current_time - created_at >= self.KEY_TTL:
                expired_users.append(username)

        cleaned_count = 0
        for username in expired_users:
            key = self._user_keys[username]["key"]
            if key in self._key_to_user:
                del self._key_to_user[key]
            del self._user_keys[username]
            cleaned_count += 1
            logger.info(f"Cleaned expired API key: {key[:8]}... (user: {username})")

        if cleaned_count > 0:
            logger.info(f"Cleaned {cleaned_count} expired API key(s)")

        return cleaned_count

    def get_all_keys(self) -> Set[str]:
        """获取所有有效的keys（用于调试，实际生产环境应谨慎使用）"""
        self.cleanup_expired_keys()
        return set(self._key_to_user.keys())

    def count(self) -> int:
        """获取当前有效的key数量（不包括过期的）"""
        self.cleanup_expired_keys()
        return len(self._key_to_user)

    def get_user_key(self, username: str) -> Optional[str]:
        """获取指定用户的API key（如果存在且未过期）

        Args:
            username: 用户名

        Returns:
            Optional[str]: API key，如果不存在或已过期则返回None
        """
        if username in self._user_keys:
            key_info = self._user_keys[username]
            key = key_info["key"]
            created_at = key_info["created_at"]

            # 检查是否过期
            if time.time() - created_at < self.KEY_TTL:
                return key

        return None


_auth_manager: Optional[AuthManager] = None
_tenant_auth_service: Optional[TenantAuthService] = None


def get_auth_manager() -> AuthManager:
    """获取全局认证管理器实例（单例模式）"""
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def get_tenant_auth_service() -> TenantAuthService:
    """获取租户 access_code 鉴权服务实例。"""
    global _tenant_auth_service
    if _tenant_auth_service is None:
        _tenant_auth_service = TenantAuthService()
    return _tenant_auth_service


def extract_api_key() -> Optional[str]:
    """从请求中提取API key

    支持以下方式：
    1. Authorization: Bearer <key>
    2. X-API-Key: <key>
    """
    # 方式1: Authorization Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 方式2: X-API-Key header
    api_key = request.headers.get("X-API-Key", "").strip()
    if api_key:
        return api_key

    return None


def require_auth(f):
    """认证装饰器 - 要求请求必须提供有效的API key

    如果配置中AUTH_ENABLED=False，则跳过认证
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        from intent_hub.config import Config

        if not Config.AUTH_ENABLED:
            return f(*args, **kwargs)

        auth_manager = get_auth_manager()
        api_key = extract_api_key()

        if not api_key:
            logger.warning(f"Request missing API key: {request.path}")
            return jsonify(
                ErrorResponse(
                    error="Authentication failed",
                    detail="Missing API key. Provide Authorization: Bearer <key> or X-API-Key: <key>",
                ).dict()
            ), 401

        # 验证API key（会自动清理过期key）
        if not auth_manager.is_valid(api_key):
            logger.warning(
                f"无效或已过期的API key: {api_key[:8]}... (请求路径: {request.path})"
            )
            return jsonify(
                ErrorResponse(
                    error="Authentication failed", detail="Invalid or expired API key, please login again"
                ).dict()
            ), 401

        return f(*args, **kwargs)

    return decorated_function


def require_telestar_auth(f):
    """Telestar 认证装饰器 - 要求请求必须提供自定义的 Predict key

    支持以下优先级的认证方式：
    1. 配置中的 PREDICT_AUTH_KEY (支持 Bearer, X-API-Key 或 原始格式)
    2. 如果启用了普通认证，则支持有效的 API Key
    如果配置中 PREDICT_AUTH_KEY 为空且未启用普通认证，则跳过认证
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否启用认证
        from intent_hub.config import Config

        predict_key = Config.PREDICT_AUTH_KEY
        auth_enabled = Config.AUTH_ENABLED

        # 如果没有设置 Predict key 且没有启用普通认证，则直接允许
        if not predict_key and not auth_enabled:
            return f(*args, **kwargs)

        # 提取 API key (支持 Bearer 或 X-API-Key)
        api_key = extract_api_key()
        # 提取原始 Authorization header (兼容某些旧调用者)
        raw_auth = request.headers.get("Authorization", "").strip()

        # 0. 允许直接使用租户 access_code 访问兼容接口
        if api_key:
            try:
                tenant_context, tenant, code = get_tenant_auth_service().authenticate_access_code(api_key)
                g.tenant_context = tenant_context
                g.current_tenant = tenant
                g.current_access_code = code
                return f(*args, **kwargs)
            except ValueError:
                pass

        # 1. 验证 Predict Key
        if predict_key:
            if api_key == predict_key or raw_auth == predict_key:
                return f(*args, **kwargs)

        # 2. 验证普通 API Key (为了方便前端测试)
        if auth_enabled:
            auth_manager = get_auth_manager()
            if api_key and auth_manager.is_valid(api_key):
                return f(*args, **kwargs)

        logger.warning(f"Predict auth failed: {request.path}")
        error_detail = "Invalid authorization."
        if predict_key:
            error_detail += f" Provide valid Predict Key in header (config: {predict_key[:2]}***)."
        if auth_enabled:
            error_detail += " Or valid API Key."

        return jsonify(
            ErrorResponse(
                error="认证失败",
                detail=error_detail,
            ).dict()
        ), 401

    return decorated_function


def require_tenant_access(f):
    """Require a valid tenant access code and attach tenant context to flask.g."""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        access_code = extract_api_key()
        if not access_code:
            return jsonify(
                ErrorResponse(
                    error="Authentication failed",
                    detail="Missing access code. Provide Authorization: Bearer <code> or X-API-Key: <code>",
                ).dict()
            ), 401

        tenant_auth_service = get_tenant_auth_service()
        try:
            tenant_context, tenant, code = tenant_auth_service.authenticate_access_code(access_code)
        except ValueError as e:
            return jsonify(
                ErrorResponse(error="Authentication failed", detail=str(e)).dict()
            ), 401

        g.tenant_context = tenant_context
        g.current_tenant = tenant
        g.current_access_code = code
        return f(*args, **kwargs)

    return decorated_function
