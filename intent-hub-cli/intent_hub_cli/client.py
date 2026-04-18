from __future__ import annotations

from typing import Any

import requests


class IntentHubClient:
    DEFAULT_TIMEOUT = 30
    LONG_RUNNING_TIMEOUT = 120

    def __init__(self, endpoint: str, access_code: str, session: requests.Session | None = None):
        self.endpoint = endpoint.rstrip("/")
        self.access_code = access_code
        self.session = session or requests.Session()

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_code}",
            "Content-Type": "application/json",
        }

    def whoami(self) -> dict[str, Any]:
        return self._request("GET", "/v1/me")

    def route(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/v1/route", json={"text": text})

    def dispatch(self, text: str) -> dict[str, Any]:
        return self._request("POST", "/v1/dispatch", json={"text": text})

    def reindex(self, force_full: bool = False) -> dict[str, Any]:
        return self._request("POST", "/tenant/reindex", json={"force_full": force_full})

    def sync_routes(self, route_ids: list[int]) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tenant/reindex/sync-route",
            json={"route_ids": route_ids},
        )

    def skills_scan_uploaded(
        self,
        *,
        source_id: str | None,
        source_label: str | None,
        client_path_hint: str | None,
        skills: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/tenant/skill-sources/scan",
            json={
                "source_id": source_id,
                "source_label": source_label,
                "client_path_hint": client_path_hint,
                "skills": skills,
            },
        )

    def _request(self, method: str, path: str, **kwargs) -> dict[str, Any]:
        response = self.session.request(
            method=method,
            url=f"{self.endpoint}{path}",
            headers=self._headers,
            timeout=self._timeout_for_path(path),
            **kwargs,
        )
        response.raise_for_status()
        return response.json()

    def _timeout_for_path(self, path: str) -> int:
        if path.startswith("/tenant/skill-") or path.startswith("/tenant/reindex"):
            return self.LONG_RUNNING_TIMEOUT
        return self.DEFAULT_TIMEOUT
