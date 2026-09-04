"""Client for the existing embedding service."""

import requests


class QwenEmbeddingEncoder:
    def __init__(self, service_url: str, timeout: int = 30, batch_size: int = 32):
        self.endpoint_url = service_url.strip()
        self.timeout = timeout
        self.batch_size = batch_size
        self._dimensions = None

    @property
    def dimensions(self) -> int:
        if self._dimensions is None:
            self._dimensions = len(self.encode_single("test"))
        return self._dimensions

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = []
        for start in range(0, len(texts), self.batch_size):
            batch = texts[start : start + self.batch_size]
            response = requests.post(
                self.endpoint_url,
                json={"inputs": batch},
                timeout=self.timeout,
            )
            response.raise_for_status()
            current = response.json()
            if not isinstance(current, list):
                raise RuntimeError("Embedding 服务返回格式不正确")
            if len(current) != len(batch):
                raise RuntimeError("Embedding 服务返回数量不匹配")
            embeddings.extend(current)
        return embeddings

    def encode_single(self, text: str) -> list[float]:
        result = self.encode([text])
        if not result:
            raise RuntimeError("Embedding 服务返回空结果")
        return result[0]

