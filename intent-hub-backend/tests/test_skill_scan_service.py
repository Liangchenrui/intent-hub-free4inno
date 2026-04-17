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


def make_source() -> SkillSourceRecord:
    return SkillSourceRecord(
        source_id="src_001",
        path="D:/skills",
        source_label="My Local Skills",
        client_path_hint="D:/skills",
        enabled=True,
        sync_mode="scan",
    )


def test_skill_scan_ingests_uploaded_skills_and_generates_drafts(test_dir):
    source = make_source()

    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)

    result = service.scan_uploaded_source(
        source=source,
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            },
            {
                "skill_name": "mail_sender",
                "relative_path": "mail_sender/SKILL.md",
                "content": "# Mail Sender\nsend mail",
            },
        ]
    )

    assert result["discovered"] == 2
    assert result["uploaded"] == 2
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert len(index["items"]) == 2
    assert {item["skill_key"] for item in index["items"]} == {
        "src_001::mail_sender/SKILL.md",
        "src_001::wiki_builder/SKILL.md",
    }
    draft_file = Path(index["items"][0]["draft_file"])
    assert draft_file.exists()


def test_skill_scan_updates_changed_uploaded_skill_only(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    source = make_source()
    service.scan_uploaded_source(
        source=source,
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    first_index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    first_hash = first_index["items"][0]["skill_hash"]

    service.scan_uploaded_source(
        source=source,
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild better wiki",
            }
        ],
    )

    second_index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    second_hash = second_index["items"][0]["skill_hash"]
    assert first_hash != second_hash


def test_skill_scan_marks_missing_uploaded_skill_as_stale(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)
    source = make_source()
    service.scan_uploaded_source(
        source=source,
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    result = service.scan_uploaded_source(source=source, uploaded_skills=[])

    assert result["stale"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    assert index["items"][0]["status"] == "stale"


def test_skill_scan_apply_mode_calls_applier_and_marks_synced(test_dir):
    context = make_context(test_dir)

    def applier(draft_payload, source, skill_file):
        return {"route_id": 42}

    service = SkillScanService(
        context,
        draft_generator=draft_generator,
        draft_applier=applier,
    )
    result = service.scan_uploaded_source(
        source=SkillSourceRecord(
            source_id="src_001",
            path="D:/skills",
            source_label="My Local Skills",
            client_path_hint="D:/skills",
            enabled=True,
            sync_mode="apply",
        ),
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    assert result["applied"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    item = index["items"][0]
    assert item["status"] == "synced"
    assert item["route_id"] == 42
    assert item["last_synced_at"]


def test_skill_scan_apply_mode_marks_skipped_when_route_exists(test_dir):
    context = make_context(test_dir)

    def applier(draft_payload, source, skill_file):
        return {"route_id": 7, "skipped": True}

    service = SkillScanService(
        context,
        draft_generator=draft_generator,
        draft_applier=applier,
    )
    result = service.scan_uploaded_source(
        source=SkillSourceRecord(
            source_id="src_001",
            path="D:/skills",
            source_label="My Local Skills",
            client_path_hint="D:/skills",
            enabled=True,
            sync_mode="apply",
        ),
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    assert result["applied"] == 1
    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    item = index["items"][0]
    assert item["status"] == "skipped"
    assert item["route_id"] == 7


def test_skill_scan_rejects_duplicate_relative_paths(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)

    with pytest.raises(ValueError, match="duplicate relative_path"):
        service.scan_uploaded_source(
            source=make_source(),
            uploaded_skills=[
                {
                    "skill_name": "wiki_builder",
                    "relative_path": "dup/SKILL.md",
                    "content": "# First\nbody",
                },
                {
                    "skill_name": "mail_sender",
                    "relative_path": "dup/SKILL.md",
                    "content": "# Second\nbody",
                },
            ],
        )


def test_skill_scan_uses_relative_path_based_draft_file_name(test_dir):
    context = make_context(test_dir)
    service = SkillScanService(context, draft_generator=draft_generator)

    service.scan_uploaded_source(
        source=make_source(),
        uploaded_skills=[
            {
                "skill_name": "wiki_builder",
                "relative_path": "folder/wiki_builder/SKILL.md",
                "content": "# Wiki Builder\nbuild wiki",
            }
        ],
    )

    index = json.loads(context.skills_index_path.read_text(encoding="utf-8"))
    draft_file = Path(index["items"][0]["draft_file"])

    assert draft_file.name == "folder__wiki_builder__SKILL.json"
