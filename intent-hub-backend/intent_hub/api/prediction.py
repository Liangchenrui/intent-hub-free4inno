"""预测相关API"""

from flask import g, jsonify

from intent_hub.auth import require_telestar_auth
from intent_hub.core.components import get_component_manager
from intent_hub.models import PredictRequest
from intent_hub.services.prediction_service import PredictionService
from intent_hub.tenant.components import TenantComponentRegistry
from intent_hub.utils.error_handler import handle_errors, validate_request


_tenant_component_registry: TenantComponentRegistry | None = None


def get_tenant_component_registry() -> TenantComponentRegistry:
    global _tenant_component_registry
    if _tenant_component_registry is None:
        _tenant_component_registry = TenantComponentRegistry()
    return _tenant_component_registry


@handle_errors
@require_telestar_auth
@validate_request(PredictRequest)
def predict(predict_req: PredictRequest):
    """路由预测接口

    输入文本，返回所有相似度大于设定阈值的路由列表，按相似度降序排列
    """
    if hasattr(g, "tenant_context"):
        component_manager = get_tenant_component_registry().get(g.tenant_context)
    else:
        component_manager = get_component_manager()
    component_manager.ensure_ready()

    prediction_service = PredictionService(component_manager)
    results = prediction_service.predict(predict_req)

    return jsonify([r.model_dump() if hasattr(r, "model_dump") else r.dict() for r in results]), 200
