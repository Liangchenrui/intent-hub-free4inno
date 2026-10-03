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


@pytest.mark.parametrize("polarity", ["positive", "negative"])
@pytest.mark.parametrize("existing", [False, True])
def test_generate_examples_respects_polarity_and_does_not_save(monkeypatch, polarity, existing):
    import json
    from langchain_core.runnables import RunnableLambda
    from intent_hub.models import GenerateUtterancesRequest, RouteConfig
    from intent_hub.services.llm_factory import LLMFactory

    components = DummyComponentManager()
    service = RouteService(components)
    if existing:
        components.route_manager.add_route(RouteConfig(id=1, name="Weather", route_key="weather", utterances=["weather"], negative_samples=["old negative"]))
    before = [r.model_dump() for r in components.route_manager.get_all_routes()]
    prompts = []
    from intent_hub.config import Config
    monkeypatch.setattr(Config, 'NEGATIVE_UTTERANCE_GENERATION_PROMPT', 'CUSTOM_NEGATIVE_TEMPLATE\n' + Config.NEGATIVE_UTTERANCE_GENERATION_PROMPT)

    def generate(prompt):
        prompts.append(prompt.to_string())
        return json.dumps({"utterances": ["weather", "old negative", " fresh one ", "fresh one", "", "fresh two", "extra"]})

    monkeypatch.setattr(LLMFactory, "create_llm", lambda: RunnableLambda(generate))
    req = GenerateUtterancesRequest(id=1 if existing else 0, name="Weather draft", route_key="weather", description="Current draft description", polarity=polarity, count=2, utterances=["weather"], negative_samples=["old negative"])
    result = service.generate_utterances(req)
    if polarity == "negative":
        assert result.negative_samples == ["old negative", "fresh one", "fresh two"]
        assert result.utterances == ["weather"]
        assert "明确不应" in prompts[0]
        assert 'CUSTOM_NEGATIVE_TEMPLATE' in prompts[0]
    else:
        assert result.utterances == ["weather", "old negative", "fresh one"]
    assert "Current draft description" in prompts[0]
    assert [r.model_dump() for r in components.route_manager.get_all_routes()] == before


def test_generation_defaults_to_positive_and_rejects_invalid_polarity():
    from pydantic import ValidationError
    from intent_hub.models import GenerateUtterancesRequest
    assert GenerateUtterancesRequest(id=0, name="test", route_key="test").polarity == "positive"
    with pytest.raises(ValidationError):
        GenerateUtterancesRequest(id=0, name="test", route_key="test", polarity="invalid")
