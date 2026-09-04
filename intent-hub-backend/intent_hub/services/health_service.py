"""Concurrent health probes for external services used by Intent Hub."""

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import requests

from intent_hub.config import Config


HEALTH_CHECK_TIMEOUT = 5


def _health_url(explicit_url: str | None, service_url: str, default_path: str) -> str:
    if explicit_url and explicit_url.strip():
        return explicit_url.strip()
    parts = urlsplit(service_url.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("service health URL must be a complete http(s) URL")
    return urlunsplit((parts.scheme, parts.netloc, default_path, "", ""))


def _probe(url: str, headers: dict[str, str] | None = None) -> dict:
    started_at = perf_counter()
    try:
        response = requests.get(
            url,
            headers=headers or {},
            timeout=HEALTH_CHECK_TIMEOUT,
        )
        latency_ms = round((perf_counter() - started_at) * 1000)
        return {
            "healthy": response.ok,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "message": "ok" if response.ok else f"HTTP {response.status_code}",
        }
    except requests.RequestException:
        return {
            "healthy": False,
            "status_code": None,
            "latency_ms": round((perf_counter() - started_at) * 1000),
            "message": "connection failed",
        }


def check_external_services() -> dict:
    targets = {
        "embedding": (
            _health_url(
                Config.EMBEDDING_HEALTH_URL,
                Config.EMBEDDING_SERVICE_URL,
                "/health",
            ),
            None,
        ),
        "qdrant": (
            _health_url(Config.QDRANT_HEALTH_URL, Config.QDRANT_URL, "/healthz"),
            {"api-key": Config.QDRANT_API_KEY} if Config.QDRANT_API_KEY else None,
        ),
    }
    with ThreadPoolExecutor(max_workers=len(targets)) as executor:
        futures = {
            name: executor.submit(_probe, url, headers)
            for name, (url, headers) in targets.items()
        }
        services = {name: future.result() for name, future in futures.items()}
    return {
        "status": (
            "ok" if all(service["healthy"] for service in services.values()) else "degraded"
        ),
        "services": services,
    }
