"""Compare a local Agent with its latest upstream snapshot."""

from __future__ import annotations

import hashlib
import json
from typing import Any


COMPARABLE_FIELDS = ("title", "text", "utterances", "negative_samples")
CORPUS_FIELDS = {"utterances", "negative_samples"}


def normalize_scalar(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_corpus(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    normalized = {normalize_scalar(item) for item in value}
    return sorted(item for item in normalized if item)


def normalized_field(field: str, value: Any) -> str | list[str]:
    return normalize_corpus(value) if field in CORPUS_FIELDS else normalize_scalar(value)


def field_fingerprint(field: str, value: Any) -> str:
    payload = json.dumps(normalized_field(field, value), ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fields_equal(field: str, left: Any, right: Any) -> bool:
    return field_fingerprint(field, left) == field_fingerprint(field, right)


def snapshots_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(fields_equal(field, left.get(field), right.get(field)) for field in COMPARABLE_FIELDS)


def comparison_summary(agent) -> dict[str, Any]:
    overrides = sorted(set(agent.manual_overrides))
    comparable_overrides = set(overrides) & set(COMPARABLE_FIELDS)
    snapshot = agent.source_snapshot or {}

    if agent.source_type == "local":
        status = "local_only"
        diff_fields: list[str] = []
        locked_equal_fields: list[str] = []
    elif agent.upstream_present is False:
        status = "upstream_missing"
        diff_fields = []
        locked_equal_fields = []
    elif agent.upstream_present is None or not all(field in snapshot for field in COMPARABLE_FIELDS):
        status = "snapshot_unknown"
        diff_fields = []
        locked_equal_fields = []
    else:
        diff_fields = [
            field for field in COMPARABLE_FIELDS
            if not fields_equal(field, getattr(agent, field), snapshot.get(field))
        ]
        locked_equal_fields = sorted(comparable_overrides - set(diff_fields))
        status = "local_modified" if diff_fields else ("locked_equal" if locked_equal_fields else "same")

    return {
        "status": status,
        "diff_fields": diff_fields,
        "diff_count": len(diff_fields),
        "override_fields": overrides,
        "locked_equal_fields": locked_equal_fields,
    }


def comparison_detail(agent, compared_at: str | None = None) -> dict[str, Any]:
    summary = comparison_summary(agent)
    snapshot = agent.source_snapshot or {}
    fields: dict[str, Any] = {}
    if agent.source_type == "upstream" and snapshot:
        for field in COMPARABLE_FIELDS:
            local_value = getattr(agent, field)
            upstream_value = snapshot.get(field)
            common = {
                "changed": field in summary["diff_fields"],
                "overridden": field in agent.manual_overrides,
            }
            if field in CORPUS_FIELDS:
                local_items = set(normalize_corpus(local_value))
                upstream_items = set(normalize_corpus(upstream_value))
                fields[field] = {
                    **common,
                    "kind": "corpus",
                    "local_count": len(local_items),
                    "upstream_count": len(upstream_items),
                    "added": sorted(local_items - upstream_items),
                    "removed": sorted(upstream_items - local_items),
                    "unchanged_count": len(local_items & upstream_items),
                }
            else:
                fields[field] = {
                    **common,
                    "kind": "scalar",
                    "local_value": local_value,
                    "upstream_value": upstream_value,
                }
    return {
        "agent_id": agent.id,
        "comparison": summary,
        "compared_at": compared_at,
        "fields": fields,
    }
