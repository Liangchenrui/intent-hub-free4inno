from types import SimpleNamespace

import pytest

from intent_hub.config import Config
from intent_hub.services.llm_service import LLMService


def recommendation_request(polarity="positive"):
    return SimpleNamespace(
        polarity=polarity,
        count=2,
        title=None,
        text=None,
        utterances=None,
        negative_samples=None,
    )


def agent():
    return SimpleNamespace(
        title="天气助手",
        text="查询天气",
        utterances=["今天天气如何"],
        negative_samples=["播放音乐"],
    )


def test_master_prompt_format_instructions_are_injected(monkeypatch):
    service = LLMService()
    captured = {}
    monkeypatch.setattr(
        Config,
        "UTTERANCE_GENERATION_PROMPT",
        "{name}|{count}|{format_instructions}",
    )

    def invoke(prompt):
        captured["prompt"] = prompt
        return {"utterances": ["查一下明天的天气", "未来一周天气"]}

    monkeypatch.setattr(service, "_invoke", invoke)

    assert service.recommendations(agent(), recommendation_request()) == [
        "查一下明天的天气",
        "未来一周天气",
    ]
    assert "format_instructions" not in captured["prompt"]
    assert '"utterances"' in captured["prompt"]


def test_unknown_prompt_variable_has_readable_error(monkeypatch):
    monkeypatch.setattr(Config, "UTTERANCE_GENERATION_PROMPT", "{skill_content}")

    with pytest.raises(ValueError, match=r"不支持的变量 \{skill_content\}"):
        LLMService().recommendations(agent(), recommendation_request())
