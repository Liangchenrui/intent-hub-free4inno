"""数据模型定义"""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class RoutePayload(BaseModel):
    """Qdrant中存储的路由载荷结构"""

    route_id: int = Field(..., description="路由ID")
    route_name: str = Field(..., description="路由名称")
    utterance: str = Field(..., description="示例语句")
    score_threshold: float = Field(..., description="相似度阈值")


class RouteConfig(BaseModel):
    """路由配置模型（用于CRUD操作）"""

    class RouteSource(BaseModel):
        type: Literal["web_manual", "json_import", "upstream_agent"] = Field(..., description="正式路由来源类型")
        source_id: Optional[str] = Field(default=None, description="来源侧稳定 ID")
        import_origin: Optional[str] = Field(default=None, description="导入来源标识")
        managed_fields: List[str] = Field(default_factory=list, description="受来源托管的字段")
        source_snapshot: Dict[str, Any] = Field(default_factory=dict, description="最近一次上游快照")
        upstream_present: Optional[bool] = Field(default=None, description="最近拉取时上游是否存在")
        last_pulled_at: Optional[str] = Field(default=None, description="最近成功拉取时间")

    class RouteSync(BaseModel):
        status: Literal["pending", "queued", "syncing", "synced", "stale", "error"] = Field(
            default="pending", description="同步状态"
        )
        last_synced_at: Optional[str] = Field(default=None, description="最近同步时间")
        version: int = Field(default=0, ge=0, description="本地路由版本")
        synced_version: int = Field(default=0, ge=0, description="已写入向量库的版本")
        task_id: Optional[str] = Field(default=None, description="当前后台同步任务 ID")
        error: Optional[str] = Field(default=None, description="最近一次同步错误")
        manual_overrides: List[str] = Field(default_factory=list, description="人工覆盖字段")

    id: int = Field(..., description="路由ID")
    name: str = Field(..., description="路由名称")
    route_key: str = Field(..., description="稳定的业务路由标识", min_length=1)
    description: str = Field(default="", description="路由描述")
    utterances: List[str] = Field(..., description="示例语句列表")
    negative_samples: List[str] = Field(
        default_factory=list,
        description="负例语句列表，用于排除不应该匹配到该路由的查询",
    )
    score_threshold: float = Field(
        default=0.75, description="相似度阈值", ge=0.0, le=1.0
    )
    negative_threshold: float = Field(
        default=0.95,
        description="负例相似度阈值，当查询与负例向量相似度超过此值时排除该路由",
        ge=0.0,
        le=1.0,
    )
    source: Optional[RouteSource] = Field(default=None, description="来源元数据")
    sync: Optional[RouteSync] = Field(default=None, description="同步元数据")
    lifecycle_status: Literal["active", "draft", "stale", "disabled"] = Field(
        default="active", description="生命周期状态"
    )


class RouteResponse(BaseModel):
    """路由匹配响应模型"""

    id: int = Field(..., description="路由ID")
    name: str = Field(..., description="路由名称")


class PredictRequest(BaseModel):
    """预测请求模型"""

    text: str = Field(..., description="待匹配的文本", min_length=1)


class PredictResponse(BaseModel):
    """预测响应模型"""

    id: int = Field(..., description="匹配到的路由ID")
    name: str = Field(..., description="匹配到的路由名称")
    route_key: str = Field(..., description="稳定的业务路由标识")
    score: Optional[float] = Field(None, description="相似度分数")


class ErrorResponse(BaseModel):
    """错误响应模型"""

    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="错误详情")


class LoginRequest(BaseModel):
    """登录请求模型"""

    username: str = Field(..., description="用户名", min_length=1)
    password: str = Field(..., description="密码", min_length=1)


class LoginResponse(BaseModel):
    """登录响应模型"""

    api_key: str = Field(..., description="API key")
    message: str = Field(
        default="请妥善保管此API key，后续请求需要在请求头中提供",
        description="提示信息",
    )


class GenerateUtterancesRequest(BaseModel):
    """生成提问请求模型"""

    id: int = Field(..., description="Agent ID")
    name: str = Field(..., description="Agent 名称")
    route_key: str = Field(..., description="业务路由标识", min_length=1)
    description: str = Field(default="", description="Agent 描述")
    count: int = Field(default=5, description="生成的提问数量", gt=0, le=50)
    utterances: Optional[List[str]] = Field(
        default=None, description="参考的utterances列表（可选）"
    )


class SkillRouteImportRequest(BaseModel):
    """通过 SKILL.md 生成路由草稿请求"""

    skill_content: str = Field(..., description="SKILL.md 文件内容", min_length=1)


class SkillRouteDraft(BaseModel):
    """从 skill 生成的路由草稿"""

    name: str = Field(..., description="路由名称")
    route_key: str = Field(..., description="业务路由标识")
    description: str = Field(default="", description="路由描述")
    utterances: List[str] = Field(..., description="建议语料列表")


class RouteImportDraft(BaseModel):
    """标准 JSON 导入草稿"""

    routes: List[RouteConfig] = Field(..., description="待导入路由列表")
    mode: Literal["merge", "replace"] = Field(default="merge", description="导入模式")


class ConflictPoint(BaseModel):
    """冲突点信息"""

    source_utterance: str = Field(..., description="源路由冲突语句")
    target_utterance: str = Field(..., description="目标路由冲突语句")
    similarity: float = Field(..., description="向量余弦相似度")


class RouteOverlap(BaseModel):
    """路由重叠诊断信息"""

    target_route_id: int = Field(..., description="目标路由ID")
    target_route_name: str = Field(..., description="目标路由名称")
    region_similarity: float = Field(..., description="区域（质心）相似度")
    instance_conflicts: List[ConflictPoint] = Field(
        default_factory=list, description="具体的向量冲突对"
    )
    total_conflicts: int = Field(default=0, description="总冲突点数量")


class DiagnosticResult(BaseModel):
    """整体诊断结果"""

    route_id: int = Field(..., description="当前查询路由ID")
    route_name: str = Field(..., description="当前查询路由名称")
    overlaps: List[RouteOverlap] = Field(default_factory=list, description="重叠详情")


class RepairSuggestion(BaseModel):
    """修复建议信息"""

    route_id: int = Field(..., description="路由ID")
    route_name: str = Field(..., description="路由名称")
    new_utterances: List[str] = Field(..., description="建议新增的强化语句")
    negative_samples: List[str] = Field(..., description="建议新增的负面约束语句")
    conflicting_utterances: List[str] = Field(
        default_factory=list, description="建议删除的冲突语句"
    )
    rationalization: str = Field(..., description="修改理由")


class RepairRequest(BaseModel):
    """修复请求模型"""

    source_route_id: int = Field(..., description="源路由ID")
    target_route_id: int = Field(..., description="目标路由ID")
    language: Literal["zh", "en"] = Field(default="zh", description="诊断意见输出语言")


class ApplyRepairRequest(BaseModel):
    """应用修复请求模型"""

    route_id: int = Field(..., description="路由ID")
    utterances: List[str] = Field(..., description="要更新的所有语句")
