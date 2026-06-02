from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.api_docs import collect_flask_routes, load_openapi_routes, parse_markdown_routes



def test_api_markdown_route_list_matches_flask_routes():
    backend_root = REPO_ROOT / "intent-hub-backend"
    routes = collect_flask_routes(backend_root)
    documented_routes = parse_markdown_routes(REPO_ROOT / "docs" / "API.md")

    assert documented_routes == routes


def test_openapi_paths_match_flask_routes():
    backend_root = REPO_ROOT / "intent-hub-backend"
    routes = collect_flask_routes(backend_root)
    openapi_routes = load_openapi_routes(REPO_ROOT / "docs" / "intent-hub-openapi.json")

    assert openapi_routes == routes
