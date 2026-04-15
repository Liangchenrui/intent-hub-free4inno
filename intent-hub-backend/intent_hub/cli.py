"""Intent Hub CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from intent_hub.client import IntentHubClient


def get_config_path() -> Path:
    return Path.home() / ".intent-hub" / "config.json"


def load_config() -> dict:
    path = get_config_path()
    if not path.exists():
        raise ValueError("Not logged in. Run `intent-hub login --endpoint ... --code ...` first.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_config(endpoint: str, access_code: str) -> None:
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"endpoint": endpoint, "access_code": access_code}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="intent-hub")
    subparsers = parser.add_subparsers(dest="command", required=True)

    login_parser = subparsers.add_parser("login")
    login_parser.add_argument("--endpoint", required=True)
    login_parser.add_argument("--code", required=True)

    subparsers.add_parser("whoami")

    route_parser = subparsers.add_parser("route")
    route_parser.add_argument("text")
    route_parser.add_argument("--json", action="store_true", dest="json_output")

    dispatch_parser = subparsers.add_parser("dispatch")
    dispatch_parser.add_argument("text")
    dispatch_parser.add_argument("--json", action="store_true", dest="json_output")

    skills_parser = subparsers.add_parser("skills")
    skills_subparsers = skills_parser.add_subparsers(dest="skills_command", required=True)
    skills_subparsers.add_parser("scan")
    apply_parser = skills_subparsers.add_parser("apply")
    apply_parser.add_argument("--draft-file", required=True)

    return parser


def _client_from_config() -> IntentHubClient:
    config = load_config()
    return IntentHubClient(endpoint=config["endpoint"], access_code=config["access_code"])


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "login":
        save_config(endpoint=args.endpoint, access_code=args.code)
        print("Saved login config")
        return 0

    client = _client_from_config()

    if args.command == "whoami":
        print(json.dumps(client.whoami(), ensure_ascii=False))
        return 0

    if args.command == "route":
        payload = client.route(args.text)
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(payload.get("route_key", ""))
        return 0

    if args.command == "dispatch":
        payload = client.dispatch(args.text)
        if args.json_output:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(payload.get("route_key", ""))
        return 0

    if args.command == "skills" and args.skills_command == "scan":
        print(json.dumps(client.skills_scan(), ensure_ascii=False))
        return 0

    if args.command == "skills" and args.skills_command == "apply":
        print(json.dumps(client.skills_apply(args.draft_file), ensure_ascii=False))
        return 0

    parser.error("Unsupported command")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
