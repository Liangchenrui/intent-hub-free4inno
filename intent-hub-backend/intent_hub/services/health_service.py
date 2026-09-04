"""Health probes for external services used by Intent Hub."""

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import requests

from intent_hub.config import Config


HEALTH_CHECK_TIMEOUT = 5


def _service_root_url(service_url: str, health_path: str) -> str:
    parts = urlsplit(service_url.strip())
    return urlunsplit((parts.scheme, parts.netloc, health_path, "", ""))


def _probe(url: str, headers: dict[str, str] | None = None) -> dict:
    started_at = perf_counter()
    try:
        response = requests.get(url, headers=headers or {}, timeout=HEALTH_CHECK_TIMEOUT)
        latency_ms = round((perf_counter() - started_at) * 1000)
        healthy = response.ok
        return {
            "healthy": healthy,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "message": "正常" if healthy else f"HTTP {response.status_code}",
        }
    except requests.RequestException as error:
        return {
            "healthy": False,
            "status_code": None,
            "latency_ms": round((perf_counter() - started_at) * 1000),
            "message": str(error),
        }


def check_external_services() -> dict:
    embedding_url = _service_root_url(Config.EMBEDDING_SERVICE_URL, "/health")
    qdrant_url = _service_root_url(Config.QDRANT_URL, "/healthz")
    qdrant_headers = {"api-key": Config.QDRANT_API_KEY} if Config.QDRANT_API_KEY else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = {
            "embedding": executor.submit(_probe, embedding_url),
            "qdrant": executor.submit(_probe, qdrant_url, qdrant_headers),
        }
        services = {name: future.result() for name, future in futures.items()}

    return {
        "status": "ok" if all(item["healthy"] for item in services.values()) else "degraded",
        "services": services,
    }
