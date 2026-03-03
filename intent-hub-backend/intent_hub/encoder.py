"""编码器模块 - 封装远程文本嵌入服务"""

import os
import time
from typing import List, Optional

import numpy as np
import requests

from intent_hub.utils.logger import logger


class QwenEmbeddingEncoder:
    """远程文本嵌入服务客户端封装类"""

    def __init__(
        self,
        service_url: str = "http://localhost:5000",
        timeout: int = 30,
        batch_size: int = 32,
    ):
        """初始化编码器客户端

        Args:
            service_url: 嵌入服务的 URL (默认为 http://localhost:5000)
            timeout: 请求超时时间 (秒)
            batch_size: 批处理大小 (用于客户端分批请求，虽然服务端可能也有批处理限制)
        """
        self.service_url = service_url.rstrip("/")
        # 支持用户直接配置完整 URL (包含 /get_embeddings)
        if self.service_url.endswith("/get_embeddings"):
            self.endpoint_url = self.service_url
        else:
            self.endpoint_url = f"{self.service_url}/get_embeddings"

        self.timeout = timeout
        self.batch_size = batch_size
        self._dimensions: Optional[int] = None

        # 验证连接并获取维度
        try:
            self._dimensions = len(self.encode_single("test"))
            logger.info(
                f"Connected to embedding service at {self.service_url}, dimensions: {self._dimensions}"
            )
        except Exception as e:
            logger.warning(f"Failed to connect to embedding service at startup: {e}")
            # 不在此处抛出异常，允许服务稍后启动

    @property
    def dimensions(self) -> int:
        """获取向量维度"""
        if self._dimensions is None:
            # 尝试重新连接
            try:
                self._dimensions = len(self.encode_single("test"))
            except Exception as e:
                raise RuntimeError(f"Embedding service unavailable: {e}")
        return self._dimensions

    def encode(self, texts: List[str]) -> List[List[float]]:
        """编码文本列表为向量

        Args:
            texts: 文本列表

        Returns:
            向量列表
        """
        if not texts:
            return []

        all_embeddings = []

        # 分批处理
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]

            try:
                response = requests.post(
                    self.endpoint_url,
                    json={"input": {"texts": batch_texts}},
                    timeout=self.timeout,
                )
                response.raise_for_status()

                result = response.json()

                # 解析响应
                # 响应格式: {"output": {"embeddings": [{"text_index": 0, "embedding": [...]}, ...]}}
                embeddings_data = result.get("output", {}).get("embeddings", [])

                # 确保按索引排序
                embeddings_data.sort(key=lambda x: x.get("text_index", 0))

                batch_embeddings = [item["embedding"] for item in embeddings_data]

                if len(batch_embeddings) != len(batch_texts):
                    logger.warning(
                        f"Expected {len(batch_texts)} embeddings, got {len(batch_embeddings)}"
                    )

                all_embeddings.extend(batch_embeddings)

            except requests.exceptions.RequestException as e:
                logger.error(f"Embedding service request failed: {e}")
                raise RuntimeError(f"Embedding service request failed: {e}")
            except (ValueError, KeyError) as e:
                logger.error(f"Invalid response from embedding service: {e}")
                raise RuntimeError(f"Invalid response from embedding service: {e}")

        return all_embeddings

    def encode_single(self, text: str) -> List[float]:
        """编码单个文本为向量

        Args:
            text: 文本字符串

        Returns:
            向量
        """
        embeddings = self.encode([text])
        if not embeddings:
            raise RuntimeError("Empty result from embedding service")
        return embeddings[0]

    def encode_to_numpy(self, texts: List[str]) -> np.ndarray:
        """编码文本列表为numpy数组

        Args:
            texts: 文本列表

        Returns:
            numpy数组
        """
        embeddings = self.encode(texts)
        return np.array(embeddings)
