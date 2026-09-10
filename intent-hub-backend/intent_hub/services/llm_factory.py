"""LLM工厂类 - 根据provider创建对应的LangChain LLM实例"""

from typing import Any, Optional

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from intent_hub.utils.logger import logger

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None
    logger.warning("langchain-google-genai not installed, Gemini support unavailable")

from intent_hub.config import Config


class LLMFactory:
    """LLM工厂类 - 根据配置创建对应的LLM实例"""

    SUPPORTED_PROVIDERS = ["deepseek", "openrouter", "doubao", "qwen", "gemini"]

    @staticmethod
    def create_llm(
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        timeout: Optional[float] = None,
        max_retries: Optional[int] = None,
        http_async_client: Optional[Any] = None,
    ) -> BaseChatModel:
        """创建LLM实例

        Args:
            provider: LLM提供商 (deepseek/openrouter/doubao/qwen/gemini)
            api_key: API密钥
            base_url: API基础URL（某些provider不需要）
            model: 模型名称
            temperature: 温度参数

        Returns:
            LangChain LLM实例

        Raises:
            ValueError: 如果provider不支持或参数不完整
        """
        # 使用配置中的默认值
        provider = provider or Config.LLM_PROVIDER
        api_key = api_key or Config.LLM_API_KEY
        base_url = base_url or Config.LLM_BASE_URL
        model = model or Config.LLM_MODEL
        temperature = temperature if temperature is not None else Config.LLM_TEMPERATURE

        if provider not in LLMFactory.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"不支持的LLM提供商: {provider}。支持的提供商: {', '.join(LLMFactory.SUPPORTED_PROVIDERS)}"
            )

        logger.info(f"Creating LLM instance: provider={provider}, model={model}")

        runtime_options = {}
        if timeout is not None:
            runtime_options["timeout"] = timeout
        if max_retries is not None:
            runtime_options["max_retries"] = max_retries
        if http_async_client is not None and provider != "gemini":
            runtime_options["http_async_client"] = http_async_client

        if provider == "gemini":
            return LLMFactory._create_gemini(api_key, model, temperature, **runtime_options)
        elif provider in ["deepseek", "openrouter", "doubao", "qwen"]:
            return LLMFactory._create_openai_compatible(
                provider, api_key, base_url, model, temperature, **runtime_options
            )
        else:
            raise ValueError(f"未实现的provider: {provider}")

    @staticmethod
    def _create_gemini(api_key: str, model: str, temperature: float, **runtime_options) -> BaseChatModel:
        """创建Gemini LLM实例"""
        if ChatGoogleGenerativeAI is None:
            raise ImportError(
                "Gemini需要安装langchain-google-genai: pip install langchain-google-genai"
            )

        if not api_key:
            raise ValueError("Gemini需要提供API密钥")

        return ChatGoogleGenerativeAI(
            model=model or "gemini-pro",
            google_api_key=api_key,
            temperature=temperature,
            **runtime_options,
        )

    @staticmethod
    def _create_openai_compatible(
        provider: str,
        api_key: str,
        base_url: Optional[str],
        model: str,
        temperature: float,
        **runtime_options,
    ) -> BaseChatModel:
        """创建OpenAI兼容的LLM实例（DeepSeek/OpenRouter/Doubao/Qwen）"""
        if not api_key:
            raise ValueError(f"{provider}需要提供API密钥")

        # 根据provider设置默认的base_url和model
        default_configs = {
            "deepseek": {
                "base_url": "https://api.deepseek.com",
                "model": "deepseek-chat",
            },
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "model": "openai/gpt-3.5-turbo",  # 默认模型，用户可自定义
            },
            "doubao": {
                "base_url": "https://ark.cn-beijing.volces.com/api/v3",
                "model": "ep-20241208123456-xxxxx",  # 示例，用户需要替换为实际模型ID
            },
            "qwen": {
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "model": "qwen-turbo",
            },
        }

        config = default_configs.get(provider, {})
        final_base_url = base_url or config.get("base_url")
        final_model = model or config.get("model")

        if not final_base_url:
            raise ValueError(f"{provider}需要提供base_url")

        if not final_model:
            raise ValueError(f"{provider}需要提供model名称")

        return ChatOpenAI(
            model=final_model,
            openai_api_key=api_key,
            openai_api_base=final_base_url,
            temperature=temperature,
            **runtime_options,
        )
