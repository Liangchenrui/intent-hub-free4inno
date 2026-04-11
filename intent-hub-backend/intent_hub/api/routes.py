"""路由管理相关API"""

from typing import List

from flask import jsonify, request
from pydantic import BaseModel, Field, ValidationError

from intent_hub.core.components import get_component_manager
from intent_hub.models import (
    ErrorResponse,
    GenerateUtterancesRequest,
    RouteConfig,
    SkillRouteImportRequest,
)
from intent_hub.services.route_service import RouteService
from intent_hub.utils.error_handler import handle_errors, validate_request
from intent_hub.utils.logger import logger


@handle_errors
def get_routes():
    """获取所有路由列表"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    routes = route_service.get_all_routes()

    return jsonify([route.dict() for route in routes]), 200


@handle_errors
def search_routes():
    """搜索路由（通过名称、描述或例句）"""
    # 获取查询参数
    query = request.args.get("q", "").strip()

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    routes = route_service.search_routes(query)

    return jsonify([route.dict() for route in routes]), 200


@handle_errors
@validate_request(RouteConfig)
def create_route(route: RouteConfig):
    """新增路由配置（含向量生成）"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)
    try:
        created_route = route_service.create_route(route)
    except ValueError as e:
        return jsonify(ErrorResponse(error="请求参数错误", detail=str(e)).dict()), 400

    return jsonify(created_route.dict()), 201


@handle_errors
def update_route(route_id: int):
    """修改指定路由"""
    # 手动验证请求数据（因为需要先获取route_id参数）
    data = request.get_json()
    if not data:
        return jsonify(
            ErrorResponse(error="请求参数错误", detail="请求体不能为空").dict()
        ), 400

    try:
        route = RouteConfig(**data)
    except ValidationError as e:
        return jsonify(
            ErrorResponse(
                error="请求参数错误", detail=f"缺少必需的参数或参数格式错误: {str(e)}"
            ).dict()
        ), 400

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        updated_route = route_service.update_route(route_id, route)
        return jsonify(updated_route.dict()), 200
    except ValueError as e:
        error = "路由不存在" if "does not exist" in str(e) else "请求参数错误"
        status = 404 if error == "路由不存在" else 400
        return jsonify(ErrorResponse(error=error, detail=str(e)).dict()), status


@handle_errors
def delete_route(route_id: int):
    """删除指定路由"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        route_service.delete_route(route_id)
        return jsonify({"message": f"路由 {route_id} 已删除"}), 200
    except ValueError as e:
        return jsonify(ErrorResponse(error="路由不存在", detail=str(e)).dict()), 404


@handle_errors
@validate_request(GenerateUtterancesRequest)
def generate_utterances(req: GenerateUtterancesRequest):
    """根据Agent信息生成提问列表（不自动持久化）"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        updated_route = route_service.generate_utterances(req)
        return jsonify(updated_route.dict()), 200
    except Exception as e:
        return jsonify(ErrorResponse(error="生成提问失败", detail=str(e)).dict()), 500


@handle_errors
@validate_request(SkillRouteImportRequest)
def import_route_from_skill(req: SkillRouteImportRequest):
    """根据 SKILL.md 内容生成路由草稿（不自动持久化）"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_service = RouteService(component_manager)

    try:
        draft = route_service.generate_route_from_skill(req)
        return jsonify(draft.dict()), 200
    except ValueError as e:
        return jsonify(ErrorResponse(error="请求参数错误", detail=str(e)).dict()), 400
    except Exception as e:
        return jsonify(ErrorResponse(error="生成路由草稿失败", detail=str(e)).dict()), 500


class ImportRoutesRequest(BaseModel):
    """导入路由请求模型

    - routes: 路由列表，元素格式等同 data/routes_config.json
    - mode:
        - merge: 默认。按 route.id 合并：存在则覆盖，不存在则新增
        - replace: 用导入结果完全替换现有路由（会删除未出现在导入列表中的路由）
    """

    routes: List[RouteConfig] = Field(..., description="要导入的路由列表")
    mode: str = Field(default="merge", description="导入模式：merge | replace")


@handle_errors
def import_routes():
    """从JSON导入路由配置（批量合并/覆盖）

    说明：
    - 该接口接受 JSON 请求体，不走 multipart 上传；前端读取文件后直接把解析结果发过来。
    - 对每条路由做 Pydantic 校验；失败则整体返回 400，并给出错误详情。
    - 导入后会同步 Qdrant 正例/负例向量，并触发增量诊断更新。
    """
    data = request.get_json()
    if not data:
        return jsonify(ErrorResponse(error="请求参数错误", detail="请求体不能为空").dict()), 400

    try:
        req = ImportRoutesRequest(**data)
    except ValidationError as e:
        return (
            jsonify(
                ErrorResponse(
                    error="请求参数错误", detail=f"参数格式错误: {str(e)}"
                ).dict()
            ),
            400,
        )

    mode = (req.mode or "merge").lower().strip()
    if mode not in ("merge", "replace"):
        return (
            jsonify(
                ErrorResponse(
                    error="请求参数错误",
                    detail="mode 仅支持 'merge' 或 'replace'",
                ).dict()
            ),
            400,
        )

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_manager = component_manager.route_manager

    existing_routes = route_manager.get_all_routes()
    existing_ids = {r.id for r in existing_routes}

    imported_ids = []
    created = 0
    updated = 0

    # 导入：逐条写入（仅更新本地 routes_config.json，不自动同步向量）
    for route in req.routes:
        # 允许导入文件中缺省 negative_threshold（前端类型是可选的）
        if getattr(route, "negative_threshold", None) is None:
            route.negative_threshold = 0.95

        # route.id==0: 走 RouteService 自动分配 ID
        if route.id == 0:
            route_service = RouteService(component_manager)
            try:
                created_route = route_service.create_route(route)
            except ValueError as e:
                return (
                    jsonify(ErrorResponse(error="请求参数错误", detail=str(e)).dict()),
                    400,
                )
            imported_ids.append(created_route.id)
            created += 1
            continue

        # route.id != 0: 如果存在则覆盖；不存在则作为“带指定ID的新建”导入
        is_update = route.id in existing_ids
        try:
            route_manager.add_route(route)
        except ValueError as e:
            return (
                jsonify(ErrorResponse(error="请求参数错误", detail=str(e)).dict()),
                400,
            )

        imported_ids.append(route.id)
        if is_update:
            updated += 1
        else:
            created += 1
            existing_ids.add(route.id)

    # replace 模式：删除未出现在导入列表中的路由（仅更新本地文件，不自动同步向量）
    removed = 0
    if mode == "replace":
        imported_set = set(imported_ids)
        to_remove = [r.id for r in route_manager.get_all_routes() if r.id not in imported_set]
        if to_remove:
            route_service = RouteService(component_manager)
            for rid in to_remove:
                try:
                    route_service.delete_route(rid)
                    removed += 1
                except Exception as e:
                    logger.error(f"Failed to delete route in replace mode (route_id={rid}): {e}")

    return (
        jsonify(
            {
                "message": "导入成功",
                "mode": mode,
                "created": created,
                "updated": updated,
                "removed": removed,
                "total": len(imported_ids),
            }
        ),
        200,
    )


class AddNegativeSamplesRequest(BaseModel):
    """添加负例样本请求模型"""

    negative_samples: List[str] = Field(..., description="负例语句列表")
    negative_threshold: float = Field(
        default=0.95,
        description="负例相似度阈值",
        ge=0.0,
        le=1.0,
    )


@handle_errors
def add_negative_samples(route_id: int):
    """为路由添加负例样本"""
    data = request.get_json()
    if not data:
        return jsonify(
            ErrorResponse(error="请求参数错误", detail="请求体不能为空").dict()
        ), 400

    try:
        req = AddNegativeSamplesRequest(**data)
    except ValidationError as e:
        return jsonify(
            ErrorResponse(
                error="请求参数错误", detail=f"参数格式错误: {str(e)}"
            ).dict()
        ), 400

    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify(ErrorResponse(error="路由不存在", detail=f"路由ID {route_id} 不存在").dict()), 404

    # 合并负例样本
    existing_negative_samples = getattr(route, 'negative_samples', [])
    new_negative_samples = list(set(existing_negative_samples + req.negative_samples))
    
    # 更新路由配置
    route.negative_samples = new_negative_samples
    route.negative_threshold = req.negative_threshold
    route_manager.add_route(route)

    return jsonify({
        "message": f"成功为路由 {route_id} 添加 {len(req.negative_samples)} 个负例样本",
        "route_id": route_id,
        "total_negative_samples": len(new_negative_samples)
    }), 200


@handle_errors
def delete_negative_samples(route_id: int):
    """删除路由的所有负例样本"""
    component_manager = get_component_manager()
    component_manager.ensure_ready()

    route_manager = component_manager.route_manager
    route = route_manager.get_route(route_id)
    if not route:
        return jsonify(ErrorResponse(error="路由不存在", detail=f"路由ID {route_id} 不存在").dict()), 404

    # 更新路由配置
    route.negative_samples = []
    route_manager.add_route(route)

    return jsonify({
        "message": f"成功删除路由 {route_id} 的所有负例样本",
        "route_id": route_id
    }), 200
