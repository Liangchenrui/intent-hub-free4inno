from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


HTTP_METHOD_ORDER = {
    "GET": 0,
    "POST": 1,
    "PUT": 2,
    "PATCH": 3,
    "DELETE": 4,
}

ROUTE_LINE_RE = re.compile(r"^- `(?P<method>GET|POST|PUT|PATCH|DELETE) (?P<path>[^`]+)`")
FLASK_VAR_RE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
AUTO_START = "<!-- BEGIN AUTO-GENERATED ROUTES -->"
AUTO_END = "<!-- END AUTO-GENERATED ROUTES -->"


@dataclass(frozen=True, order=True)
class ApiRoute:
    path: str
    method: str

    def markdown_line(self) -> str:
        return f"- `{self.method} {self.path}`"


def collect_flask_routes(backend_root: Path) -> tuple[ApiRoute, ...]:
    backend_root = backend_root.resolve()
    sys.path.insert(0, str(backend_root))
    try:
        from intent_hub.app import app
    finally:
        try:
            sys.path.remove(str(backend_root))
        except ValueError:
            pass

    routes: list[ApiRoute] = []
    for rule in app.url_map.iter_rules():
        if rule.endpoint == "static":
            continue
        path = _normalize_path(rule.rule)
        for method in rule.methods or ():
            if method in {"HEAD", "OPTIONS"}:
                continue
            routes.append(ApiRoute(path=path, method=method))
    return _sort_routes(routes)


def parse_markdown_routes(path: Path) -> tuple[ApiRoute, ...]:
    routes: list[ApiRoute] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        match = ROUTE_LINE_RE.match(line.strip())
        if match:
            routes.append(
                ApiRoute(
                    path=_normalize_path(match.group("path")),
                    method=match.group("method"),
                )
            )
    return _sort_routes(routes)


def load_openapi_routes(path: Path) -> tuple[ApiRoute, ...]:
    document = json.loads(path.read_text(encoding="utf-8"))
    routes: list[ApiRoute] = []
    for raw_path, operations in document.get("paths", {}).items():
        for method in operations:
            upper_method = method.upper()
            if upper_method in HTTP_METHOD_ORDER:
                routes.append(ApiRoute(path=_normalize_path(raw_path), method=upper_method))
    return _sort_routes(routes)


def render_markdown_routes(routes: Iterable[ApiRoute]) -> str:
    sections = [
        ("Admin APIs", lambda route: route.path == "/auth/login" or route.path.startswith("/admin/")),
        ("Tenant Runtime APIs", lambda route: route.path.startswith("/v1/")),
        ("Tenant Control-Plane APIs", lambda route: route.path.startswith("/tenant/")),
        ("Compatibility Endpoints", lambda route: _is_compatibility_path(route.path)),
    ]
    lines: list[str] = []
    route_list = list(routes)
    for title, predicate in sections:
        matching = [route for route in route_list if predicate(route)]
        if not matching:
            continue
        lines.append(f"### {title}")
        lines.append("")
        lines.extend(route.markdown_line() for route in matching)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_api_markdown(path: Path, routes: Iterable[ApiRoute]) -> None:
    content = path.read_text(encoding="utf-8")
    generated = render_markdown_routes(routes).rstrip()
    replacement = f"{AUTO_START}\n{generated}\n{AUTO_END}"
    if AUTO_START not in content or AUTO_END not in content:
        raise ValueError(f"{path} does not contain generated route markers")
    updated = re.sub(
        rf"{re.escape(AUTO_START)}.*?{re.escape(AUTO_END)}",
        replacement,
        content,
        flags=re.DOTALL,
    )
    path.write_text(updated, encoding="utf-8")


def compare_routes(expected: tuple[ApiRoute, ...], actual: tuple[ApiRoute, ...]) -> str:
    expected_set = set(expected)
    actual_set = set(actual)
    missing = _sort_routes(expected_set - actual_set)
    extra = _sort_routes(actual_set - expected_set)
    lines: list[str] = []
    if missing:
        lines.append("Missing routes:")
        lines.extend(f"  {route.method} {route.path}" for route in missing)
    if extra:
        lines.append("Extra routes:")
        lines.extend(f"  {route.method} {route.path}" for route in extra)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check or update API documentation route lists.")
    parser.add_argument("command", choices=["check", "update-api-md"])
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    backend_root = repo_root / "intent-hub-backend"
    api_md = repo_root / "docs" / "API.md"
    openapi_json = repo_root / "docs" / "intent-hub-openapi.json"

    flask_routes = collect_flask_routes(backend_root)

    if args.command == "update-api-md":
        update_api_markdown(api_md, flask_routes)
        return 0

    markdown_diff = compare_routes(flask_routes, parse_markdown_routes(api_md))
    openapi_diff = compare_routes(flask_routes, load_openapi_routes(openapi_json))
    if markdown_diff or openapi_diff:
        if markdown_diff:
            print("docs/API.md is out of sync with Flask routes:")
            print(markdown_diff)
        if openapi_diff:
            print("docs/intent-hub-openapi.json is out of sync with Flask routes:")
            print(openapi_diff)
        return 1
    return 0


def _normalize_path(path: str) -> str:
    return FLASK_VAR_RE.sub(r"{\1}", path)


def _sort_routes(routes: Iterable[ApiRoute]) -> tuple[ApiRoute, ...]:
    return tuple(
        sorted(
            routes,
            key=lambda route: (route.path, HTTP_METHOD_ORDER.get(route.method, 99), route.method),
        )
    )


def _is_compatibility_path(path: str) -> bool:
    return path == "/predict" or path.startswith("/routes") or path.startswith("/reindex") or path.startswith(
        "/diagnostics"
    ) or path == "/settings"


if __name__ == "__main__":
    raise SystemExit(main())
