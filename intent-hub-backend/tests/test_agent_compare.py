from intent_hub.agent_compare import comparison_detail, comparison_summary
from intent_hub.models import Agent
from intent_hub.services.sync_service import agent_hash


def upstream_agent(**values):
    snapshot = {
        "title": "天气助手",
        "text": "查询天气\n预报",
        "utterances": ["北京天气", "上海天气"],
        "negative_samples": ["播放音乐"],
    }
    data = {
        "id": 1,
        "title": snapshot["title"],
        "text": snapshot["text"],
        "utterances": snapshot["utterances"],
        "negative_samples": snapshot["negative_samples"],
        "source_snapshot": snapshot,
        "upstream_present": True,
    }
    data.update(values)
    return Agent(**data)


def test_comparison_normalizes_scalar_and_ignores_corpus_order_duplicates():
    agent = upstream_agent(
        title="  天气助手 ",
        text="查询天气\r\n预报  ",
        utterances=[" 上海天气 ", "北京天气", "北京天气"],
    )
    assert comparison_summary(agent)["status"] == "same"


def test_equal_override_is_reported_as_locked_not_modified():
    agent = upstream_agent(manual_overrides=["title"])
    summary = comparison_summary(agent)
    assert summary["status"] == "locked_equal"
    assert summary["locked_equal_fields"] == ["title"]
    assert summary["diff_fields"] == []


def test_detail_reports_actual_corpus_additions_and_removals():
    agent = upstream_agent(
        utterances=["北京天气", "广州天气"],
        manual_overrides=["utterances"],
    )
    detail = comparison_detail(agent, "2026-07-21T00:00:00+00:00")
    diff = detail["fields"]["utterances"]
    assert detail["comparison"]["status"] == "local_modified"
    assert diff["added"] == ["广州天气"]
    assert diff["removed"] == ["上海天气"]
    assert diff["unchanged_count"] == 1


def test_source_state_statuses_take_priority():
    assert comparison_summary(Agent(id=-1, title="本地", source_type="local"))["status"] == "local_only"
    assert comparison_summary(upstream_agent(upstream_present=False))["status"] == "upstream_missing"
    assert comparison_summary(Agent(id=2, title="旧数据"))["status"] == "snapshot_unknown"


def test_vector_hash_ignores_corpus_order_and_duplicate_whitespace():
    first = upstream_agent(utterances=["北京天气", "上海天气"])
    second = upstream_agent(utterances=[" 上海天气 ", "北京天气", "北京天气"])
    assert agent_hash(first) == agent_hash(second)
