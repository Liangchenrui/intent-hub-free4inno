"""HTTP and persistence models."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: int
    title: str
    text: str = ""
    utterances: list[str] = Field(default_factory=list)
    negative_samples: list[str] = Field(default_factory=list)
    score_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    negative_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)
    source_type: Literal["upstream", "local"] = "upstream"
    upstream_id: int | None = None
    upstream_present: bool | None = None
    manual_overrides: list[str] = Field(default_factory=list)
    lifecycle_status: Literal["active", "inactive", "deleted"] = "active"
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    updated_at: str | None = None


class AgentUpdate(BaseModel):
    title: str | None = None
    text: str | None = None
    utterances: list[str] | None = None
    negative_samples: list[str] | None = None
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    negative_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    lifecycle_status: Literal["active", "inactive", "deleted"] | None = None


class AgentCreate(BaseModel):
    title: str = Field(..., min_length=1)
    text: str = ""
    utterances: list[str] = Field(default_factory=list)
    negative_samples: list[str] = Field(default_factory=list)
    score_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    negative_threshold: float = Field(default=0.95, ge=0.0, le=1.0)


class RecommendationRequest(BaseModel):
    polarity: Literal["positive", "negative"]
    count: int = Field(default=5, ge=1, le=20)
    title: str | None = None
    text: str | None = None
    utterances: list[str] | None = None
    negative_samples: list[str] | None = None


class ConflictPoint(BaseModel):
    source_utterance: str
    target_utterance: str
    similarity: float


class RouteOverlap(BaseModel):
    target_route_id: int
    target_route_name: str
    region_similarity: float
    instance_conflicts: list[ConflictPoint] = Field(default_factory=list)
    total_conflicts: int = 0


class DiagnosticResult(BaseModel):
    route_id: int
    route_name: str
    overlaps: list[RouteOverlap] = Field(default_factory=list)


class RepairRequest(BaseModel):
    source_route_id: int
    target_route_id: int


class ApplyRepairRequest(BaseModel):
    route_id: int
    utterances: list[str]
    negative_samples: list[str] | None = None


class MergeAgentsRequest(BaseModel):
    source_agent_id: int
    target_agent_id: int
    title: str = Field(..., min_length=1)
    text: str = ""


class RouteRequest(BaseModel):
    query: str = Field(..., min_length=1)


class ThresholdRequest(BaseModel):
    score_threshold: float = Field(..., ge=0.0, le=1.0)
    negative_threshold: float = Field(..., ge=0.0, le=1.0)
