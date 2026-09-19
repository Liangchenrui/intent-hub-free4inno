"""Read-only adapter for the optional upstream Agent API."""

import ast
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import requests

from intent_hub.config import Config


class AgentSource:
    def __init__(self, session=None, label_ids=None, base_url=None, workers=None):
        self.session = session
        self.label_ids = label_ids
        self.base_url = base_url
        self._auto_workers = workers is None
        self.workers = max(1, min(8, workers if workers is not None else 8))
        self._local = threading.local()
        self._sessions = []
        self.failed_ids = []
        self.listed_ids = set()
        self.complete = True
        self.request_count = self.detail_request_count = 0
        self._stats_lock = threading.Lock()

    def fetch_all(self) -> list[dict[str, Any]]:
        try:
            return self._fetch_all()
        finally:
            for session in self._sessions:
                session.close()
            self._sessions.clear()
            self._local = threading.local()

    def _fetch_all(self):
        self.failed_ids, self.listed_ids, self.complete = [], set(), True
        self.request_count = self.detail_request_count = 0
        # Sessions keep cookies/headers thread-local while urllib3's thread-safe
        # pool reuses the connection already opened by the list request.
        self._adapter = requests.adapters.HTTPAdapter(pool_connections=2, pool_maxsize=self.workers, pool_block=True)
        base_url = str(self.base_url if self.base_url is not None else Config.AGENT_API_URL or "").strip().rstrip("/")
        label_ids = [item.strip() for item in str(self.label_ids if self.label_ids is not None else Config.AGENT_API_LABEL_IDS or "").split(",") if item.strip()]
        if not base_url or not label_ids:
            raise ValueError("请先配置 AGENT_API_URL 和 AGENT_API_LABEL_IDS")

        records_by_id: dict[str, dict] = {}
        for label_id in label_ids:
            payload = self._get(base_url, "/resource/search", {"labels": label_id})
            records = payload.get("records")
            if not isinstance(records, list):
                raise ValueError("上游列表缺少 records 数组")
            total = payload.get("total")
            page = payload.get('pageNum')
            page_size = payload.get('pageSize')
            # pageNum/pageSize were verified against the live read-only API.
            if total is not None and int(total) > len(records) and page == 1 and page_size:
                records = list(records)
                seen = {str((r.get('resource') or {}).get('id')) for r in records}
                while len(records) < int(total):
                    page += 1
                    more = self._get(base_url, '/resource/search',
                                     {'labels': label_id, 'pageNum': page, 'pageSize': page_size})
                    batch = more.get('records')
                    if not isinstance(batch, list):
                        raise ValueError('上游分页缺少 records 数组')
                    ids = {str((r.get('resource') or {}).get('id')) for r in batch}
                    if not batch or ids & seen or more.get('total') != total or more.get('pageNum') != page:
                        self.complete = False
                        break
                    seen.update(ids)
                    records.extend(batch)
            if total is not None and int(total) > len(records):
                self.complete = False
            if payload.get("hasMore") or payload.get("has_more") or payload.get("next"):
                self.complete = False
            for record in records:
                resource_id = (record.get("resource") or {}).get("id")
                if resource_id is not None:
                    records_by_id[str(resource_id)] = record
                else:
                    self.complete = False

        self.listed_ids = set(records_by_id)
        def fetch_one(source_id):
            try:
                details = records_by_id[source_id]["resource"]
                # A routing-complete list is not necessarily a complete raw Agent.
                # BUPT returns raw details, including fields absent from live lists.
                if not all(key in details for key in ("title", "text", "extent00", "extent01",
                                                     "attachments", "author", "labelsByCategory", "parameters", "source")):
                    details = self._get(base_url, f"/resource/{source_id}/detail")
                if str(details.get("id", source_id)) != source_id:
                    raise ValueError("上游详情 ID 不匹配")
                if not all(key in details for key in ("title", "text", "extent00", "extent01")):
                    raise ValueError("上游详情缺少必要字段")
                return {
                    "source_id": source_id,
                    "route_key": details.get("route_key") or details.get("routeKey") or str(details.get("title") or "").strip(),
                    "details": details,
                    "name": str(details.get("title") or "").strip(),
                    "description": str(details.get("text") or "").strip(),
                    "utterances": self._parse_corpus(details.get("extent00")),
                    "negative_samples": self._parse_corpus(details.get("extent01")),
                }, None
            except Exception:
                return None, source_id
        # With the live 8-Agent source, parallel TLS setup was slower than one
        # reused connection. Keep small pulls serial; bound larger pulls at 8.
        concurrency = 1 if self._auto_workers and len(records_by_id) <= 8 else self.workers
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            results = list(executor.map(fetch_one, records_by_id))
        self.failed_ids = [failed for _, failed in results if failed is not None]
        return [agent for agent, _ in results if agent is not None]

    def _get(self, base_url: str, path: str, params=None) -> dict[str, Any]:
        with self._stats_lock:
            self.request_count += 1
            self.detail_request_count += int(path.endswith('/detail'))
        session = self.session
        if session is None:
            if not hasattr(self._local, "session"):
                self._local.session = requests.Session()
                self._local.session.mount('https://', self._adapter)
                self._local.session.mount('http://', self._adapter)
                self._sessions.append(self._local.session)
            session = self._local.session
        response = session.get(
            f"{base_url}{path}",
            params=params,
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 200 or not isinstance(payload.get("data"), dict):
            raise RuntimeError(payload.get("msg") or "上游 Agent API 返回异常")
        return payload["data"]

    @staticmethod
    def _parse_corpus(value: Any) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str) and value.strip():
            try:
                items = json.loads(value)
            except json.JSONDecodeError:
                try:
                    items = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    raise ValueError('上游语料格式无效')
        else:
            return []
        if not isinstance(items, list):
            raise ValueError('上游语料必须为数组')
        return list(dict.fromkeys(str(item).strip() for item in items if str(item).strip()))
