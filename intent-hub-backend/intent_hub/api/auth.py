"""认证相关API"""

from flask import jsonify
from intent_hub.utils.logger import logger

from intent_hub.auth import get_auth_manager
from intent_hub.models import ErrorResponse, LoginRequest, LoginResponse
from intent_hub.utils.error_handler import handle_errors, validate_request


@handle_errors
@validate_request(LoginRequest)
def login(login_req: LoginRequest):
    """登录接口 - 验证用户名密码后生成API key（免鉴权）

    请求体需要包含：
    {
        "username": "your_username",
        "password": "your_password"
    }
    """
    # 验证用户名和密码
    auth_manager = get_auth_manager()
    if not auth_manager.verify_user(login_req.username, login_req.password):
        logger.warning(f"Login failed: invalid username or password (user: {login_req.username})")
        return jsonify(
            ErrorResponse(error="认证失败", detail="用户名或密码错误").dict()
        ), 401

    api_key = auth_manager.generate_key(login_req.username)
    logger.info(
        f"用户 {login_req.username} 登录成功，API key: {api_key[:8]}...，当前有效key数量: {auth_manager.count()}"
    )

    return jsonify(
        LoginResponse(
            api_key=api_key,
            message="请妥善保管此API key，后续请求需要在请求头中提供 Authorization: Bearer <key> 或 X-API-Key: <key>",
        ).dict()
    ), 200
