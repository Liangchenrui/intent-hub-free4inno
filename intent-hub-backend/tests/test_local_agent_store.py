from pathlib import Path

from intent_hub.agent_store import AgentStore
from intent_hub.models import Agent


def upstream(agent_id=7, title="上游名称", utterances=None):
    return Agent(
        id=agent_id,
        title=title,
        text="上游描述",
        utterances=utterances or ["语料一"],
        negative_samples=["负例一"],
        details={"id": agent_id},
    )


def test_sqlite_store_migrates_json_idempotently(tmp_path: Path):
    legacy = tmp_path / "agents.json"
    legacy.write_text(upstream().model_dump_json(), encoding="utf-8")
    # Legacy snapshots are arrays.
    legacy.write_text(f"[{legacy.read_text(encoding='utf-8')}]", encoding="utf-8")
    store = AgentStore(tmp_path / "agents.db", legacy)
    assert store.get(7).title == "上游名称"
    assert store.get(7).upstream_id == 7
    assert len(AgentStore(tmp_path / "agents.db", legacy).all()) == 1


def test_pull_preserves_manual_fields_and_disables_missing(tmp_path: Path):
    store = AgentStore(tmp_path / "agents.db")
    store.merge_upstream([upstream(), upstream(8, "将被停用")])
    store.update(7, {"title": "人工名称", "utterances": ["人工语料"]})
    result = store.merge_upstream([upstream(7, "新上游名称", ["新上游语料"])])
    current = store.get(7)
    assert current.title == "人工名称"
    assert current.utterances == ["人工语料"]
    assert current.source_snapshot["title"] == "新上游名称"
    assert current.upstream_present is True
    assert store.get(8).lifecycle_status == "inactive"
    assert store.get(8).upstream_present is False
    assert result["disabled"] == 1
    assert result["upstream_changed"] == 1
    assert result["upstream_missing"] == 1


def test_pull_counts_unchanged_agents_and_missing_only_once(tmp_path: Path):
    store = AgentStore(tmp_path / "agents.db")
    first = store.merge_upstream([upstream(), upstream(8, "将被移除")])
    assert first["created"] == 2
    second = store.merge_upstream([upstream()])
    assert second["unchanged"] == 1
    assert second["updated"] == 0
    assert second["upstream_missing"] == 1
    third = store.merge_upstream([upstream()])
    assert third["upstream_missing"] == 0


def test_restore_upstream_fields_and_local_negative_ids(tmp_path: Path):
    store = AgentStore(tmp_path / "agents.db")
    store.merge_upstream([upstream()])
    store.update(7, {"title": "人工名称"})
    assert store.restore_fields(7, ["title"]).title == "上游名称"
    first = store.create_local(title="本地一", utterances=[])
    second = store.create_local(title="本地二", utterances=[])
    assert (first.id, second.id) == (-1, -2)
