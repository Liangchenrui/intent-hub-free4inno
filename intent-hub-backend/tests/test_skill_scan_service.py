import json
import shutil
from pathlib import Path
from uuid import uuid4

import pytest

from intent_hub.platform.models import SkillSourceRecord, TenantRecord
from intent_hub.platform.workspace import TenantWorkspaceResolver
from intent_hub.services.skill_scan_service import SkillScanService
from intent_hub.tenant.context import TenantContext


@pytest.fixture
def test_dir():
    path = Path(__file__).parent / ".tmp" / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


def make_context(test_dir: Path) -> TenantContext:
    tenant = TenantRecord(
        tenant_id="team_alpha",
        name="Team Alpha",
        status="active",
        qdrant_collection="intent_hub_team_alpha",
        access_codes=[],
        skill_sources=[],
    )
    workspace = TenantWorkspaceResolver(test_dir, tenant).resolve()
    return TenantContext.from_tenant_record(tenant, workspace)


def draft_generator(skill_path: Path, content: str) -> dict:
    route_key = skill_path.parent.name.replace("_", ".")
    return {
        "mode": "merge",
        "routes": [
            {
                "id": 0,
                "name": skill_path.parent.name,
                "route_key": route_key,
                "description": content.splitlines()[0],
                "utterances": [f"use {skill_path.parent.name}"],
                "negative_samples": [],
                "score_threshold": 0.75,
                "negative_threshold": 0.95,
                "source": {
                    "type": "json_import",
                    "import_origin": "skill_scan",
                    "managed_fields": [],
                },
                "sync": {"status": "pending", "last_synced_at": None, "manual_overrides": []},
                "lifecycle_status": "active",
            }
        ],
    }


def test_skill_scan_discovers_skills_and_generates_drafts(test_dir):
    skills_root = test_dir / "skills"
    (skills_root / "wiki_builder").mkdir(parents=True, exist_ok=True)
    (skills_root / "wiki_builder" / "SKILL.md").write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")
    (skills_root / "mail_sender").mkdir(parents=True, exist_ok=True)
    (skills_root / "mail_sender" / "SKILL.md").write_text("# Mail Sender\nsend mail", encoding="utf-8")

    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)

    result = service.scan_sources(
        [
            SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft")
        ]
    )

    assert result["discovered"] == 2
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert len(index["items"]) == 2
    draft_file = Path(index["items"][0]["draft_file"])
    assert draft_file.exists()


def test_skill_scan_updates_changed_skill_only(test_dir):
    skills_root = test_dir / "skills"
    skill_dir = skills_root / "wiki_builder"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")

    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    service.scan_sources([SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft")])

    first_index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    first_hash = first_index["items"][0]["skill_hash"]

    skill_file.write_text("# Wiki Builder\nbuild better wiki", encoding="utf-8")
    service.scan_sources([SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft")])

    second_index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    second_hash = second_index["items"][0]["skill_hash"]
    assert first_hash != second_hash


def test_skill_scan_marks_deleted_skill_as_stale(test_dir):
    skills_root = test_dir / "skills"
    skill_dir = skills_root / "wiki_builder"
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")

    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    service.scan_sources([SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft")])

    skill_file.unlink()
    result = service.scan_sources([SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="draft")])

    assert result["stale"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert index["items"][0]["status"] == "stale"


def test_skill_scan_apply_mode_calls_applier_and_marks_synced(test_dir):
    skills_root = test_dir / "skills"
    skill_dir = skills_root / "wiki_builder"
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text("# Wiki Builder\nbuild wiki", encoding="utf-8")

    context = make_context(test_dir)

    def applier(draft_payload, source, skill_file):
        return {"route_id": 42}

    service = SkillScanService(
        context,
        draft_generator=draft_generator,
        draft_applier=applier,
    )
    result = service.scan_sources(
        [SkillSourceRecord(source_id="src_001", path=str(skills_root), enabled=True, sync_mode="apply")]
    )

    assert result["applied"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    item = index["items"][0]
    assert item["status"] == "synced"
    assert item["route_id"] == 42
    assert item["last_synced_at"]
