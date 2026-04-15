"""路由服务测试"""

from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.models import RouteImportDraft, SkillRouteImportRequest
from intent_hub.route_manager import RouteManager
from intent_hub.services.route_service import RouteService


class DummyComponentManager:
    def __init__(self):
        self.route_manager = RouteManager(
            config_path=str(Path(__file__).parent / ".tmp" / f"{uuid4().hex}.json")
        )

    def ensure_ready(self):
        return None


def test_build_skill_route_key_candidate_normalizes_whitespace():
    """基于名称生成的兜底 route_key 会规整空白"""
    assert RouteService._build_skill_route_key_candidate("  Weather   Query  ") == "weather.query"


def test_build_skill_route_key_candidate_uses_default_when_empty():
    """空名称会返回兜底 route_key"""
    assert RouteService._build_skill_route_key_candidate("") == "skill.imported"


def test_normalize_generated_utterances_deduplicates_and_strips():
    """LLM 返回的语料会去空白和重复"""
    result = RouteService._normalize_generated_utterances(
        ["  查天气  ", "", "查天气", "帮我查天气", "   "]
    )

    assert result == ["查天气", "帮我查天气"]


def test_generate_route_from_skill_returns_standard_import_draft(monkeypatch):
    service = RouteService(DummyComponentManager())

    monkeypatch.setattr(
        service,
        "_invoke_skill_route_generation",
        lambda skill_content: service._draft_output_model(
            name="Obsidian Wiki Builder",
            route_key="obsidian.wiki.build",
            description="构建和整理 wiki",
            utterances=["整理 wiki", "构建知识库"],
        ),
    )

    draft = service.generate_route_from_skill(
        SkillRouteImportRequest(skill_content="# SKILL\nbuild wiki")
    )

    assert isinstance(draft, RouteImportDraft)
    assert draft.mode == "merge"
    assert draft.routes[0].source is not None
    assert draft.routes[0].source.type == "json_import"
    assert draft.routes[0].source.import_origin == "skill_import"
