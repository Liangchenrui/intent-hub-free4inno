"""路由服务 - 处理路由CRUD业务逻辑"""

from typing import List

from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field

from intent_hub.core.components import ComponentManager
from intent_hub.models import GenerateUtterancesRequest, RouteConfig
from intent_hub.services.llm_factory import LLMFactory
from intent_hub.utils.logger import logger


class UtteranceList(BaseModel):
    utterances: List[str] = Field(description="生成的提问列表")


class RouteService:
    """路由服务类 - 处理路由的CRUD操作"""

    def __init__(self, component_manager: ComponentManager):
        """初始化路由服务

        Args:
            component_manager: 组件管理器实例
        """
        self.component_manager = component_manager

    def get_all_routes(self) -> List[RouteConfig]:
        """获取所有路由配置

        Returns:
            路由配置列表
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        routes = route_manager.get_all_routes()
        logger.info(f"Fetched {len(routes)} routes")
        logger.debug(
            f"路由详情: {[{'id': r.id, 'name': r.name, 'utterances_count': len(r.utterances)} for r in routes]}"
        )
        return routes

    def search_routes(self, query: str) -> List[RouteConfig]:
        """搜索路由配置

        Args:
            query: 搜索关键词，会在名称、描述和例句中搜索

        Returns:
            匹配的路由配置列表
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        routes = route_manager.search_routes(query)
        logger.info(f"Search for '{query}': {len(routes)} matches found")
        logger.debug(f"Matched routes: {[{'id': r.id, 'name': r.name} for r in routes]}")
        return routes

    def create_route(self, route: RouteConfig) -> RouteConfig:
        """创建或更新路由（仅更新本地配置文件，不自动同步向量）

        Args:
            route: 路由配置

        Returns:
            创建或更新后的路由配置

        Raises:
            ValueError: 如果ID不为0且路由不存在
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        if route.id == 0:
            routes = route_manager.get_all_routes()
            valid_ids = [r.id for r in routes if r.id != 0]

            if not valid_ids:
                new_id = 1
            else:
                new_id = max(valid_ids) + 1

            route.id = new_id
            logger.info(
                f"ID 0 detected, creating new route with ID: {route.id}"
            )
        else:
            if not route_manager.get_route(route.id):
                raise ValueError(
                    f"Route ID {route.id} does not exist. Set ID to 0 to create new."
                )
            logger.info(f"Updating route ID: {route.id}")

        route_manager.add_route(route)
        logger.info(f"Route saved: {route.name} (ID: {route.id})")

        return route

    def update_route(self, route_id: int, route: RouteConfig) -> RouteConfig:
        """更新指定路由（仅更新本地配置文件，不自动同步向量）

        Args:
            route_id: 路由ID
            route: 新的路由配置

        Returns:
            更新后的路由配置

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        if not route_manager.update_route(route_id, route):
            raise ValueError(f"Route ID {route_id} does not exist")
        logger.info(f"Route updated: {route.name} (ID: {route_id})")

        return route

    def delete_route(self, route_id: int) -> None:
        """删除指定路由（仅更新本地配置文件，不自动同步向量）

        Args:
            route_id: 路由ID

        Raises:
            ValueError: 如果路由不存在
        """
        self.component_manager.ensure_ready()

        route_manager = self.component_manager.route_manager

        if not route_manager.delete_route(route_id):
            raise ValueError(f"Route ID {route_id} does not exist")
        logger.info(f"Route deleted: ID {route_id}")

    def generate_utterances(self, req: GenerateUtterancesRequest) -> RouteConfig:
        """根据 Agent 信息生成提问列表（不执行持久化，由前端决定是否保存）

        Args:
            req: 生成请求

        Returns:
            生成的路由配置（包含示例utterances在最前面 + 新生成的utterances）
        """
        self.component_manager.ensure_ready()
        route_manager = self.component_manager.route_manager

        example_utterances = req.utterances if req.utterances is not None else []
        new_utterances = self._generate_utterances_with_llm(req, example_utterances)
        final_utterances = example_utterances + new_utterances

        logger.info(
            f"Generated {len(new_utterances)} utterances for ID {req.id} (Total: {len(final_utterances)})"
        )

        existing_route = route_manager.get_route(req.id) if req.id != 0 else None

        if existing_route:
            return RouteConfig(
                id=req.id,
                name=req.name if req.name else existing_route.name,
                description=req.description
                if req.description
                else existing_route.description,
                utterances=final_utterances,
                negative_samples=getattr(existing_route, 'negative_samples', []),
                score_threshold=existing_route.score_threshold,
                negative_threshold=getattr(existing_route, 'negative_threshold', 0.95),
            )
        else:
            return RouteConfig(
                id=req.id,
                name=req.name,
                description=req.description,
                utterances=final_utterances,
                negative_samples=[],
                score_threshold=0.75,  # 默认阈值
                negative_threshold=0.95,  # 默认负例阈值
            )

    def _generate_utterances_with_llm(
        self, req: GenerateUtterancesRequest, example_utterances: List[str]
    ) -> List[str]:
        """使用LangChain和配置的LLM生成提问

        Args:
            req: 生成请求
            example_utterances: 示例utterances列表（用于参考风格，不会包含在返回结果中）

        Returns:
            新生成的utterances列表（不包含示例）
        """
        llm = LLMFactory.create_llm()

        parser = PydanticOutputParser(pydantic_object=UtteranceList)

        reference_utterances_text = ""
        if example_utterances:
            utterances_list = "\n".join([f"- {utt}" for utt in example_utterances])
            reference_utterances_text = f"\n参考示例（请参照这些示例的风格和范围，生成新的句子，但绝对不能重复这些示例）:\n{utterances_list}\n"

        from intent_hub.config import Config
        prompt = PromptTemplate(
            template=Config.UTTERANCE_GENERATION_PROMPT,
            input_variables=["name", "description", "count", "reference_utterances"],
            partial_variables={"format_instructions": parser.get_format_instructions()},
        )

        prompt_variables = {
            "name": req.name,
            "description": req.description,
            "count": req.count,
            "reference_utterances": reference_utterances_text,
        }

        chain = prompt | llm | parser

        try:
            result = chain.invoke(prompt_variables)
            generated_utterances = result.utterances

            reference_set = set(example_utterances) if example_utterances else set()
            new_utterances = []
            for utt in generated_utterances:
                if utt not in reference_set:
                    new_utterances.append(utt)

            if len(new_utterances) > req.count:
                new_utterances = new_utterances[: req.count]

            return new_utterances
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise RuntimeError(f"LLM generation failed: {str(e)}")
