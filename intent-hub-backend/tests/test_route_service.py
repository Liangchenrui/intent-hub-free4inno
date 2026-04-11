"""路由服务测试"""

from intent_hub.services.route_service import RouteService


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
