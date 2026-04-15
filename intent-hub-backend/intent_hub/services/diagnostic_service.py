import json
import os
import threading
from typing import Any, Dict, List, Optional

import numpy as np

from intent_hub.config import Config
from intent_hub.core.components import ComponentManager
from intent_hub.models import (
    ConflictPoint,
    DiagnosticResult,
    RepairSuggestion,
    RouteOverlap,
)
from intent_hub.utils.logger import logger

try:
    import umap  # type: ignore
except Exception:  # pragma: no cover
    umap = None


class DiagnosticService:
    """诊断服务 - 处理语义重叠检测逻辑"""

    # 诊断阈值定义（从 Config 读取，提供默认值）
    @property
    def REGION_THRESHOLD_SIGNIFICANT(self) -> float:
        """区域重叠：显著（路由级冲突阈值）"""
        return getattr(Config, "REGION_THRESHOLD_SIGNIFICANT", 0.85)

    REGION_THRESHOLD_SEVERE = 0.95  # 区域重叠：严重（保留用于未来扩展）

    @property
    def INSTANCE_THRESHOLD_AMBIGUOUS(self) -> float:
        """向量冲突：模糊歧义（语料级冲突阈值）"""
        return getattr(Config, "INSTANCE_THRESHOLD_AMBIGUOUS", 0.92)

    INSTANCE_THRESHOLD_HARD = 0.98  # 向量冲突：硬冲突（保留用于未来扩展）

    # 当 AGENT_REPAIR_PROMPT 为空时使用的默认提示词，必须要求 LLM 只输出 JSON
    DEFAULT_REPAIR_PROMPT = """你是一个意图路由修复助手。给定两个发生冲突的路由及其冲突示例，请为路由A生成修复建议。

## 输入信息
- 路由A名称: {name_a}
- 路由A描述: {desc_a}
- 路由A示例话术: {utterances_a}
- 路由B名称: {name_b}
- 路由B描述: {desc_b}
- 冲突示例: {conflicts}

## 输出要求
你必须且仅输出一个合法的 JSON 对象，不要输出任何解释、前缀或后缀文字。JSON 必须包含且仅包含以下四个键：
- new_utterances: 字符串数组，建议为路由A新增的、能强化与路由B区分度的话术
- negative_samples: 字符串数组，建议的负面约束话术（用户说这些时不应匹配路由A）
- conflicting_utterances: 字符串数组，建议从路由A中删除的、与路由B冲突的话术
- rationalization: 字符串，简要说明修改理由（一句话）

直接输出 JSON，不要用 markdown 代码块包裹。"""

    def __init__(self, component_manager: ComponentManager):
        self.component_manager = component_manager
        tenant_context = getattr(component_manager, "context", None)
        if tenant_context is not None and getattr(tenant_context, "diagnostics_cache_path", None):
            self.cache_path = str(tenant_context.diagnostics_cache_path)
        else:
            # 兼容旧单租户入口
            self.cache_path = Config.DIAGNOSTICS_CACHE_PATH
        # 确保目录存在
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)

    def _load_cache(self) -> Dict[str, Any]:
        """从文件加载诊断缓存"""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load diagnostic cache: {e}")
        return {}

    def _save_cache(self, cache_data: Dict[str, Any]):
        """将诊断数据保存到缓存文件"""
        try:
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save diagnostic cache: {e}")

    def _cosine_similarity(self, v1: np.ndarray, v2: np.ndarray) -> float:
        """计算余弦相似度"""
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(v1, v2) / (norm1 * norm2))

    def analyze_route_overlap(
        self, route_id: int, max_conflicts: Optional[int] = None
    ) -> DiagnosticResult:
        """分析指定路由与其他所有路由的语义重叠情况"""
        self.component_manager.ensure_ready()
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        # 1. 获取当前路由信息
        current_route = route_manager.get_route(route_id)
        if not current_route:
            raise ValueError(f"路由ID {route_id} 不存在")

        # 2. 获取当前路由的所有向量并计算质心
        current_points = qdrant_client.get_route_vectors(route_id)
        if not current_points:
            return DiagnosticResult(
                route_id=route_id, route_name=current_route.name, overlaps=[]
            )

        # 排除负例语料：如果一个语料在 negative_samples 中，即使它在 utterances 中，也要排除
        current_negative_samples = set(
            getattr(current_route, "negative_samples", []) or []
        )
        current_points_filtered = [
            p
            for p in current_points
            if p["payload"].get("utterance", "") not in current_negative_samples
        ]

        if not current_points_filtered:
            return DiagnosticResult(
                route_id=route_id, route_name=current_route.name, overlaps=[]
            )

        current_vectors = [np.array(p["vector"]) for p in current_points_filtered]
        centroid_current = np.mean(current_vectors, axis=0)

        # 3. 获取所有其他路由
        all_routes = route_manager.get_all_routes()
        overlaps = []

        for other_route in all_routes:
            if other_route.id == route_id:
                continue

            # 获取对方路由的向量
            other_points = qdrant_client.get_route_vectors(other_route.id)
            if not other_points:
                continue

            # 排除对方路由的负例语料
            other_negative_samples = set(
                getattr(other_route, "negative_samples", []) or []
            )
            other_points_filtered = [
                p
                for p in other_points
                if p["payload"].get("utterance", "") not in other_negative_samples
            ]

            if not other_points_filtered:
                continue

            other_vectors = [np.array(p["vector"]) for p in other_points_filtered]
            centroid_other = np.mean(other_vectors, axis=0)

            # A. 区域重叠：计算两个质心之间的相似度 (Region Overlap)
            centroid_sim = self._cosine_similarity(centroid_current, centroid_other)

            # B. 向量冲突：计算点对点相似度 (Instance Conflict)
            instance_conflicts = []
            for p_curr in current_points_filtered:
                v_curr = np.array(p_curr["vector"])
                u_curr = p_curr["payload"].get("utterance", "")

                for p_other in other_points_filtered:
                    v_other = np.array(p_other["vector"])
                    u_other = p_other["payload"].get("utterance", "")

                    sim = self._cosine_similarity(v_curr, v_other)
                    if sim >= self.INSTANCE_THRESHOLD_AMBIGUOUS:
                        instance_conflicts.append(
                            ConflictPoint(
                                source_utterance=u_curr,
                                target_utterance=u_other,
                                similarity=sim,
                            )
                        )

            # 按相似度降序排序
            instance_conflicts.sort(key=lambda x: x.similarity, reverse=True)

            # 记录冲突总数
            total_conflicts = len(instance_conflicts)

            # 如果指定了限制，则截断
            if max_conflicts is not None:
                instance_conflicts = instance_conflicts[:max_conflicts]

            # 如果质心重叠显著，或者存在向量冲突，则记录
            if centroid_sim >= self.REGION_THRESHOLD_SIGNIFICANT or instance_conflicts:
                overlaps.append(
                    RouteOverlap(
                        target_route_id=other_route.id,
                        target_route_name=other_route.name,
                        region_similarity=centroid_sim,
                        instance_conflicts=instance_conflicts,
                        total_conflicts=total_conflicts,
                    )
                )

        # 按区域重叠分值降序排序
        overlaps.sort(key=lambda x: x.region_similarity, reverse=True)

        return DiagnosticResult(
            route_id=route_id, route_name=current_route.name, overlaps=overlaps
        )

    def analyze_all_overlaps(
        self, use_cache: bool = True, max_conflicts_per_pair: Optional[int] = None
    ) -> List[DiagnosticResult]:
        """对所有路由进行全局重叠检测"""
        if use_cache:
            cache = self._load_cache()
            if cache:
                logger.info("Reading diagnostic result from cache")
                results = []
                for r_id_str, r_data in cache.items():
                    res = DiagnosticResult(**r_data)
                    if res.overlaps:
                        # 在此处也应用 max_conflicts_per_pair 限制
                        if max_conflicts_per_pair is not None:
                            for overlap in res.overlaps:
                                overlap.total_conflicts = len(
                                    overlap.instance_conflicts
                                )
                                overlap.instance_conflicts = overlap.instance_conflicts[
                                    :max_conflicts_per_pair
                                ]
                        results.append(res)
                return results

        # 如果不使用缓存，则重新计算
        self.component_manager.ensure_ready()
        all_routes = self.component_manager.route_manager.get_all_routes()

        results = []
        cache_to_save = {}
        for route in all_routes:
            # 计算时不应用限制，以便完整缓存
            result = self.analyze_route_overlap(route.id)
            cache_to_save[str(route.id)] = result.dict()

            # 返回结果时应用限制
            if max_conflicts_per_pair is not None:
                for overlap in result.overlaps:
                    overlap.total_conflicts = len(overlap.instance_conflicts)
                    overlap.instance_conflicts = overlap.instance_conflicts[
                        :max_conflicts_per_pair
                    ]

            if result.overlaps:
                results.append(result)

        # 保存到缓存
        self._save_cache(cache_to_save)
        return results

    def update_route_diagnostics(self, route_id: int):
        """增量更新指定路由的诊断信息"""
        logger.info(f"Incremental update diagnostics for route ID {route_id}")
        cache = self._load_cache()

        # 1. 计算当前路由的最新诊断结果
        current_result = self.analyze_route_overlap(route_id)
        cache[str(route_id)] = current_result.dict()

        # 2. 更新其他路由中关于当前路由的重叠信息
        self.component_manager.ensure_ready()
        qdrant_client = self.component_manager.qdrant_client
        route_manager = self.component_manager.route_manager

        current_points = qdrant_client.get_route_vectors(route_id)
        if current_points:
            # 排除负例语料
            current_route = route_manager.get_route(route_id)
            current_negative_samples = (
                set(getattr(current_route, "negative_samples", []) or [])
                if current_route
                else set()
            )
            current_points_filtered = [
                p
                for p in current_points
                if p["payload"].get("utterance", "") not in current_negative_samples
            ]

            if current_points_filtered:
                current_vectors = [
                    np.array(p["vector"]) for p in current_points_filtered
                ]
                centroid_current = np.mean(current_vectors, axis=0)
            else:
                centroid_current = None

            for other_id_str, other_data in cache.items():
                other_id = int(other_id_str)
                if other_id == route_id:
                    continue

                # 获取对方路由的向量，计算它与当前修改路由的重叠情况
                other_points = qdrant_client.get_route_vectors(other_id)
                if not other_points:
                    continue

                # 排除对方路由的负例语料
                other_route = route_manager.get_route(other_id)
                other_negative_samples = (
                    set(getattr(other_route, "negative_samples", []) or [])
                    if other_route
                    else set()
                )
                other_points_filtered = [
                    p
                    for p in other_points
                    if p["payload"].get("utterance", "") not in other_negative_samples
                ]

                if not other_points_filtered or centroid_current is None:
                    continue

                other_vectors = [np.array(p["vector"]) for p in other_points_filtered]
                centroid_other = np.mean(other_vectors, axis=0)

                # A. 区域重叠
                centroid_sim = self._cosine_similarity(centroid_other, centroid_current)

                # B. 向量冲突 (注意这里是 other 作为 source, current 作为 target)
                instance_conflicts = []
                for p_other in other_points_filtered:
                    v_other = np.array(p_other["vector"])
                    u_other = p_other["payload"].get("utterance", "")
                    for p_curr in current_points_filtered:
                        v_curr = np.array(p_curr["vector"])
                        u_curr = p_curr["payload"].get("utterance", "")
                        sim = self._cosine_similarity(v_other, v_curr)
                        if sim >= self.INSTANCE_THRESHOLD_AMBIGUOUS:
                            instance_conflicts.append(
                                ConflictPoint(
                                    source_utterance=u_other,
                                    target_utterance=u_curr,
                                    similarity=sim,
                                )
                            )

                # 更新 other_data 中的 overlaps 列表
                other_res = DiagnosticResult(**other_data)
                other_res.overlaps = [
                    o for o in other_res.overlaps if o.target_route_id != route_id
                ]

                # 如果存在重叠，添加新记录
                if (
                    centroid_sim >= self.REGION_THRESHOLD_SIGNIFICANT
                    or instance_conflicts
                ):
                    other_res.overlaps.append(
                        RouteOverlap(
                            target_route_id=route_id,
                            target_route_name=current_result.route_name,
                            region_similarity=centroid_sim,
                            instance_conflicts=instance_conflicts,
                        )
                    )
                    # 重新排序
                    other_res.overlaps.sort(
                        key=lambda x: x.region_similarity, reverse=True
                    )

                # 更新缓存中的数据
                cache[other_id_str] = other_res.dict()

        # 3. 保存更新后的缓存
        self._save_cache(cache)

    def run_async_diagnostics(self, mode: str, route_id: Optional[int] = None):
        """异步执行诊断任务"""

        def _task():
            try:
                if mode == "incremental" and route_id is not None:
                    self.update_route_diagnostics(route_id)
                elif mode == "full":
                    self.analyze_all_overlaps(use_cache=False)
                logger.info(
                    f"Async diagnostics completed: mode={mode}, route_id={route_id}"
                )
            except Exception as e:
                logger.error(f"Async diagnostics failed: {e}")

        thread = threading.Thread(target=_task)
        thread.start()

    def remove_route_from_cache(self, route_id: int):
        """从诊断缓存中移除指定路由"""
        logger.info(f"Removed route ID {route_id} from diagnostic cache")
        cache = self._load_cache()

        # 1. 移除该路由自身的记录
        cache.pop(str(route_id), None)

        # 2. 从其他路由的 overlaps 列表中移除该路由
        for other_id_str, other_data in cache.items():
            if "overlaps" in other_data:
                other_data["overlaps"] = [
                    o
                    for o in other_data["overlaps"]
                    if o.get("target_route_id") != route_id
                ]

        # 3. 保存更新后的缓存
        self._save_cache(cache)

    def build_umap_projection(
        self, n_neighbors: int = 15, min_dist: float = 0.1, seed: int = 42
    ) -> Dict[str, Any]:
        """对 Qdrant 中所有点进行 UMAP 降维，返回 2D 坐标（用于可视化）"""
        self.component_manager.ensure_ready()
        qdrant_client = self.component_manager.qdrant_client

        if umap is None:
            raise RuntimeError("未安装 umap-learn，无法进行 UMAP 降维")

        # 排除负例向量，只获取正例向量用于诊断和可视化
        all_points = qdrant_client.scroll_all_points(
            with_vectors=True, exclude_negative=True
        )
        if not all_points:
            return {
                "points": [],
                "meta": {
                    "n_points": 0,
                    "n_neighbors": n_neighbors,
                    "min_dist": min_dist,
                },
            }

        vectors = []
        payloads = []
        for p in all_points:
            v = p.get("vector")
            pl = p.get("payload") or {}
            if v is None:
                continue
            if pl.get("route_id") is None:
                continue
            # 双重检查：确保不是负例向量
            if pl.get(qdrant_client.IS_NEGATIVE_KEY, False):
                continue
            vectors.append(np.array(v, dtype=np.float32))
            payloads.append(pl)

        if not vectors:
            return {
                "points": [],
                "meta": {
                    "n_points": 0,
                    "n_neighbors": n_neighbors,
                    "min_dist": min_dist,
                },
            }

        X = np.vstack(vectors)
        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=n_neighbors,
            min_dist=min_dist,
            metric="cosine",
            random_state=seed,
        )

        Y = reducer.fit_transform(X)

        out_points = []
        for (x, y), pl in zip(Y, payloads):
            out_points.append(
                {
                    "x": float(x),
                    "y": float(y),
                    "route_id": int(pl.get("route_id")),
                    "route_name": str(pl.get("route_name") or ""),
                    "utterance": str(pl.get("utterance") or ""),
                }
            )

        return {
            "points": out_points,
            "meta": {
                "n_points": len(out_points),
                "n_neighbors": n_neighbors,
                "min_dist": min_dist,
            },
        }

    def get_repair_suggestions(
        self, source_route_id: int, target_route_id: int
    ) -> RepairSuggestion:
        """使用 LLM 为冲突的两个路由生成修复建议"""
        from langchain_core.output_parsers import JsonOutputParser
        from langchain_core.prompts import ChatPromptTemplate

        from intent_hub.services.llm_factory import LLMFactory

        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        route_a = route_manager.get_route(source_route_id)
        route_b = route_manager.get_route(target_route_id)

        if not route_a or not route_b:
            raise ValueError("指定的路由不存在")

        # 获取冲突示例
        overlap_info = self.analyze_route_overlap(source_route_id)
        target_overlap = next(
            (o for o in overlap_info.overlaps if o.target_route_id == target_route_id),
            None,
        )
        # 将 ConflictPoint 转化为字符串描述
        conflict_examples = []
        if target_overlap:
            for c in target_overlap.instance_conflicts[:5]:
                conflict_examples.append(
                    f"'{c.source_utterance}' 与对方的 '{c.target_utterance}' 冲突 (相似度: {c.similarity:.4f})"
                )

        llm = LLMFactory.create_llm(temperature=0.7)

        from intent_hub.config import Config

        prompt_text = (Config.AGENT_REPAIR_PROMPT or "").strip()
        if not prompt_text:
            prompt_text = self.DEFAULT_REPAIR_PROMPT
        prompt = ChatPromptTemplate.from_messages([("system", prompt_text)])

        chain = prompt | llm | JsonOutputParser()

        try:
            result = chain.invoke(
                {
                    "name_a": route_a.name,
                    "desc_a": route_a.description,
                    "utterances_a": route_a.utterances[:10],
                    "name_b": route_b.name,
                    "desc_b": route_b.description,
                    "conflicts": conflict_examples,
                }
            )

            return RepairSuggestion(
                route_id=source_route_id,
                route_name=route_a.name,
                new_utterances=result.get("new_utterances", []),
                negative_samples=result.get("negative_samples", []),
                conflicting_utterances=result.get("conflicting_utterances", []),
                rationalization=result.get("rationalization", ""),
            )
        except Exception as e:
            logger.error(f"LLM repair suggestion failed: {str(e)}")
            raise RuntimeError(f"修复建议生成失败: {str(e)}")

    def apply_repair(self, route_id: int, utterances: List[str]) -> bool:
        """应用修复建议（仅更新本地 routes_config.json，不自动同步向量）"""
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        route = route_manager.get_route(route_id)
        if not route:
            raise ValueError(f"路由ID {route_id} 不存在")

        # 1. 更新 route_manager (内存/文件)
        route.utterances = utterances
        route_manager.update_route(route.id, route)

        return True
