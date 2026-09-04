"""Compare a local route with its latest upstream snapshot."""

from __future__ import annotations

import hashlib
import json
from typing import Any


COMPARABLE_FIELDS = ("name", "description", "utterances", "negative_samples")
CORPUS_FIELDS = {"utterances", "negative_samples"}


def normalize_scalar(value: Any) -> str:
    return str(value or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def normalize_corpus(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    values = {normalize_scalar(item) for item in value}
    return sorted(item for item in values if item)


def field_fingerprint(field: str, value: Any) -> str:
    normalized = normalize_corpus(value) if field in CORPUS_FIELDS else normalize_scalar(value)
    payload = json.dumps(normalized, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def fields_equal(field: str, left: Any, right: Any) -> bool:
    return field_fingerprint(field, left) == field_fingerprint(field, right)


def snapshots_equal(left: dict[str, Any], right: dict[str, Any]) -> bool:
    return all(fields_equal(field, left.get(field), right.get(field)) for field in COMPARABLE_FIELDS)


def comparison_summary(route) -> dict[str, Any]:
    source = route.source
    if source is None or source.type != "upstream_agent":
        return {"status": "local_only", "diff_fields": [], "diff_count": 0, "override_fields": []}
    overrides = sorted(set(route.sync.manual_overrides if route.sync else []))
    snapshot = source.source_snapshot or {}
    if source.upstream_present is False:
        status, diff_fields = "upstream_missing", []
    elif not all(field in snapshot for field in COMPARABLE_FIELDS):
        status, diff_fields = "snapshot_unknown", []
    else:
        diff_fields = [field for field in COMPARABLE_FIELDS if not fields_equal(field, getattr(route, field), snapshot.get(field))]
        locked_equal = bool(set(overrides) - set(diff_fields))
        status = "local_modified" if diff_fields else ("locked_equal" if locked_equal else "same")
    return {
        "status": status,
        "diff_fields": diff_fields,
        "diff_count": len(diff_fields),
        "override_fields": overrides,
    }


def comparison_detail(route) -> dict[str, Any]:
    summary = comparison_summary(route)
    snapshot = route.source.source_snapshot if route.source else {}
    fields = {}
    for field in COMPARABLE_FIELDS:
        local_value = getattr(route, field)
        upstream_value = snapshot.get(field)
        common = {"changed": field in summary["diff_fields"], "overridden": field in summary["override_fields"]}
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
            fields[field] = {**common, "kind": "scalar", "local_value": local_value, "upstream_value": upstream_value}
    return {
        "route_id": route.id,
        "comparison": summary,
        "compared_at": route.source.last_pulled_at if route.source else None,
        "fields": fields,
    }
