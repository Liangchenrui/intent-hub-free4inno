"""Skill directory scan and draft generation service."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from intent_hub.platform.models import SkillSourceRecord
from intent_hub.tenant.context import TenantContext


class SkillScanService:
    """Scan configured skills roots and maintain skills_index.json."""

    def __init__(self, tenant_context: TenantContext, draft_generator=None, draft_applier=None):
        self.tenant_context = tenant_context
        self.draft_generator = draft_generator
        self.draft_applier = draft_applier

    def scan_sources(self, skill_sources: list[SkillSourceRecord]) -> dict:
        index = self._load_index()
        active_items: dict[str, dict] = {}
        discovered = 0
        updated = 0
        applied = 0
        now = self._utc_now()

        for source in skill_sources:
            if not source.enabled:
                continue
            for skill_file in sorted(Path(source.path).glob("*/SKILL.md")):
                discovered += 1
                key = str(skill_file.resolve())
                content = skill_file.read_text(encoding="utf-8")
                skill_hash = self._hash_text(content)
                existing = index.get(key)
                item = dict(existing or {})
                item["source_id"] = source.source_id
                item["skill_path"] = key
                item["skill_hash"] = skill_hash
                item["last_scanned_at"] = now
                item["status"] = "pending"

                if existing is None or existing.get("skill_hash") != skill_hash:
                    draft_payload = self._generate_draft(skill_file, content)
                    draft_path = self._draft_file_path(source.source_id, skill_file.parent.name)
                    draft_path.parent.mkdir(parents=True, exist_ok=True)
                    draft_path.write_text(
                        json.dumps(draft_payload, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    item["draft_file"] = str(draft_path)
                    item["json_hash"] = self._hash_text(
                        json.dumps(draft_payload, ensure_ascii=False, sort_keys=True)
                    )
                    if source.sync_mode == "apply":
                        if self.draft_applier is None:
                            raise RuntimeError("draft_applier is required for sync_mode=apply")
                        apply_result = self.draft_applier(
                            draft_payload=draft_payload,
                            source=source,
                            skill_file=skill_file,
                        )
                        if isinstance(apply_result, dict) and apply_result.get("skipped"):
                            item["status"] = "skipped"
                        else:
                            item["status"] = "synced"
                        item["last_synced_at"] = now
                        if isinstance(apply_result, dict):
                            route_id = apply_result.get("route_id")
                            if isinstance(route_id, int):
                                item["route_id"] = route_id
                        applied += 1
                    updated += 1
                else:
                    item["draft_file"] = existing.get("draft_file")
                    item["json_hash"] = existing.get("json_hash")
                    item["last_synced_at"] = existing.get("last_synced_at")
                    item["route_id"] = existing.get("route_id")

                active_items[key] = item

        stale = 0
        for key, item in index.items():
            if key in active_items:
                continue
            stale_item = dict(item)
            stale_item["status"] = "stale"
            active_items[key] = stale_item
            stale += 1

        self._save_index({"items": list(active_items.values())})
        return {"discovered": discovered, "updated": updated, "stale": stale, "applied": applied}

    def scan_uploaded_source(self, source: SkillSourceRecord, uploaded_skills: list[dict]) -> dict:
        index = self._load_index()
        active_items: dict[str, dict] = {}
        discovered = len(uploaded_skills)
        updated = 0
        applied = 0
        stale = 0
        now = self._utc_now()
        seen_paths: set[str] = set()

        for payload in uploaded_skills:
            relative_path = self._normalize_relative_path(payload["relative_path"])
            if relative_path in seen_paths:
                raise ValueError(f"duplicate relative_path: {relative_path}")
            seen_paths.add(relative_path)
            content = payload["content"]
            key = f"{source.source_id}::{relative_path}"
            existing = index.get(key)
            item = dict(existing or {})
            item["source_id"] = source.source_id
            item["source_label"] = source.source_label
            item["skill_key"] = key
            item["skill_name"] = self._resolve_skill_name(payload, relative_path)
            item["relative_path"] = relative_path
            item["client_path_hint"] = payload.get("client_path_hint") or source.client_path_hint
            item["skill_hash"] = self._hash_text(content)
            item["last_scanned_at"] = now
            item["status"] = "pending"

            if existing is None or existing.get("skill_hash") != item["skill_hash"]:
                draft_payload = self._generate_draft(Path(relative_path), content)
                draft_path = self._draft_file_path(source.source_id, relative_path)
                draft_path.parent.mkdir(parents=True, exist_ok=True)
                draft_path.write_text(
                    json.dumps(draft_payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
                item["draft_file"] = str(draft_path)
                item["json_hash"] = self._hash_text(
                    json.dumps(draft_payload, ensure_ascii=False, sort_keys=True)
                )
                if source.sync_mode == "apply":
                    if self.draft_applier is None:
                        raise RuntimeError("draft_applier is required for sync_mode=apply")
                    apply_result = self.draft_applier(
                        draft_payload=draft_payload,
                        source=source,
                        skill_file=Path(relative_path),
                    )
                    if isinstance(apply_result, dict) and apply_result.get("skipped"):
                        item["status"] = "skipped"
                    else:
                        item["status"] = "synced"
                    item["last_synced_at"] = now
                    if isinstance(apply_result, dict):
                        route_id = apply_result.get("route_id")
                        if isinstance(route_id, int):
                            item["route_id"] = route_id
                    applied += 1
                updated += 1
            else:
                item["draft_file"] = existing.get("draft_file")
                item["json_hash"] = existing.get("json_hash")
                item["last_synced_at"] = existing.get("last_synced_at")
                item["route_id"] = existing.get("route_id")

            active_items[key] = item

        for key, item in index.items():
            if item.get("source_id") == source.source_id:
                if key in active_items:
                    continue
                stale_item = dict(item)
                stale_item["status"] = "stale"
                active_items[key] = stale_item
                stale += 1
                continue
            active_items[key] = item

        self._save_index({"items": list(active_items.values())})
        return {
            "discovered": discovered,
            "uploaded": discovered,
            "updated": updated,
            "stale": stale,
            "applied": applied,
            "skipped": 0,
            "errors": [],
        }

    def _load_index(self) -> dict[str, dict]:
        path = self.tenant_context.skills_index_path
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        items = {}
        for item in payload.get("items", []):
            key = item.get("skill_key") or item.get("skill_path")
            if key:
                items[key] = item
        return items

    def _save_index(self, payload: dict) -> None:
        self.tenant_context.skills_index_path.parent.mkdir(parents=True, exist_ok=True)
        self.tenant_context.skills_index_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _draft_file_path(self, source_id: str, relative_path: str) -> Path:
        slug = relative_path.replace("\\", "/").strip("/").replace("/", "__").replace(".md", "")
        return self.tenant_context.imports_dir / "skills" / source_id / f"{slug}.json"

    def _generate_draft(self, skill_file: Path, content: str) -> dict:
        if self.draft_generator is None:
            raise RuntimeError("draft_generator is required for skill scanning")
        return self.draft_generator(skill_file, content)

    @staticmethod
    def _normalize_relative_path(relative_path: str) -> str:
        normalized = (relative_path or "").replace("\\", "/").strip("/")
        if not normalized or not normalized.endswith("SKILL.md"):
            raise ValueError("relative_path must point to SKILL.md")
        return normalized

    @staticmethod
    def _resolve_skill_name(payload: dict, relative_path: str) -> str:
        skill_name = (payload.get("skill_name") or "").strip()
        if skill_name:
            return skill_name
        parts = [part for part in relative_path.split("/") if part]
        if len(parts) >= 2:
            return parts[-2]
        return "SKILL"

    @staticmethod
    def _hash_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
