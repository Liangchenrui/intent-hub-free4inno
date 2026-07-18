"""Minimal API models."""

from typing import Any

from pydantic import BaseModel, Field


class Agent(BaseModel):
    id: int
    title: str
    text: str = ""
    utterances: list[str] = Field(default_factory=list)
    negative_samples: list[str] = Field(default_factory=list)
    score_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    negative_threshold: float = Field(default=0.95, ge=0.0, le=1.0)
    details: dict[str, Any]


class RouteRequest(BaseModel):
    query: str = Field(..., min_length=1)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ThresholdRequest(BaseModel):
    score_threshold: float = Field(..., ge=0.0, le=1.0)
    negative_threshold: float = Field(..., ge=0.0, le=1.0)
