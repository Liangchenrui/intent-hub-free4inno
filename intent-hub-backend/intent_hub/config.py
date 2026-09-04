"""配置管理模块"""

import json
from pathlib import Path
from typing import Any, Dict, Optional

from intent_hub.utils.logger import logger


_current_file = Path(__file__).resolve()
_backend_root = _current_file.parent.parent

# 统一使用后端目录下的 data 文件夹
PROJECT_ROOT = _backend_root
DATA_DIR = PROJECT_ROOT / "data"

# 新创建 settings.json 时写入的默认提示词
DEFAULT_UTTERANCE_GENERATION_PROMPT = """你是一个资深的用户意图分析专家。你的任务是为特定的 AI Agent 生成高质量的测试数据集（Utterances），用于后续的意图识别和路由分发系统训练。 ### Agent 背景信息 - **Agent 名称**: {name} - **功能描述**: {description} - **参考示例（请参照这些示例的风格和范围，生成新的句子，但绝对不能重复这些示例）**: {reference_utterances} ### 生成要求 你需要生成 {count} 条**全新的**用户提问（必须与参考示例不同），请严格遵守以下准则： 1. **分布控制**：    - **关键词/短语 (50%)**: 极其简短，如"查天气"、"翻译一下"、"写代码"。这类词对路由最关键。    - **简单指令 (50%)**: 直接的命令句，如"帮我写个请假条"、"帮我分析这行代码"。 2. **多样性与覆盖面**：    - 提取描述中的"核心动词" and "核心名词"，进行交叉组合。    - 包含同义词替换（例如：从"预定"扩展到"帮我订一个"、"我想约一个"）。    - 必须沿用参考示例的语气和专业深度，但不要重复原话。 3. **路由判别性**：    - 生成的提问必须与该 Agent 的核心功能高度相关，避免产生可能导致路由误判到其他通用 Agent 的极其模糊的句子。 4. **格式要求**：    - 仅输出生成的问题列表，不要包含任何解释性文字。 {format_instructions}"""

DEFAULT_AGENT_REPAIR_PROMPT = """## 角色设定 你是一个**资深的 NLU / 用户意图分析专家**。 ## 任务背景 当前系统中 {name_a} 与 {name_b} 在语义空间中存在显著重叠，导致路由模型出现误判。 你的任务是通过生成**高质量、强判别性的语料**，对 {name_a} 进行**语义修复**，强化其可识别特征，并主动规避 {name_b} 的语义边界。 --- ## 意图背景信息 ### {name_a} - **名称**: {name_a} - **描述**: {desc_a} - **参考示例（仅用于风格与范围参考，禁止复用或改写）**: {utterances_a} ### {name_b} - **名称**: {name_b} - **描述**: {desc_b} ### 高频冲突例句（真实误判样本） {conflicts} --- ## 生成要求（必须严格遵守） ### 1. 语料生成数量与分布（仅适用于 new_utterances） 为 {name_a} 生成 **5 条全新的用户提问**，并严格控制以下比例： - **关键词 / 短语（≈50%）** - 极简、去语境、偏触发式 - 明确体现 {name_a} 的**核心动词 / 核心名词** - **简单指令（≈50%）** - 清晰、直接的命令式表达 - 明确指向 {name_a} 的**能力边界** --- ### 2. 判别性与修复导向（核心要求） - 明确**强化 {name_a} 的专属特征词、操作对象或约束条件** - **显式避开**： - {name_b} 的核心动词 - {name_b} 的典型对象 - 容易引发歧义的抽象或泛化表达 - 所有新例句必须落在 {name_a} 的**安全语义区**内 --- ### 3. 负面约束样本（negative_samples） 生成 **3 条负面约束例句**，要求： - 表面上与 {name_a} **高度相似** - 但由于**关键动词 / 对象 / 目标发生偏移** - **语义上明确不属于 {name_a}** - 用于训练模型：**不要将这些输入路由到 {name_a}** --- ### 4. 多样性要求 - 对 {name_a} 的**核心动词、核心名词**进行同义替换 - 覆盖不同句式与指令粒度 - 保持与参考示例一致的**语气与专业深度** - **禁止**复用、拼接或轻微改写任何已有示例 --- ## 输出格式（必须严格一致） 请**仅**按以下 JSON 格式输出，不要包含任何解释性文字或多余字段：
json
{{
  "new_utterances": [
    "生成的全新例句 1",
    "生成的全新例句 2",
    "生成的全新例句 3",
    "生成的全新例句 4",
    "生成的全新例句 5"
  ],
  "negative_samples": [
    "负面约束例句 1",
    "负面约束例句 2",
    "负面约束例句 3"
  ],
  "rationalization": "简要说明本次修复如何强化 `{name_a}` 的判别特征，并与 `{name_b}` 拉开语义距离"
}}

注意：
- 输出中不得包含任何除上述 JSON 以外的内容
- 所有生成句子必须是全新且未出现过的"""

DEFAULT_SKILL_ROUTE_IMPORT_PROMPT = """你是一个资深的意图路由设计专家。你的任务是读取用户上传的 `SKILL.md` 内容，为意图路由系统提炼一个新的路由实体草稿。

## 目标
基于 skill 文档内容，提炼并生成：
1. `name`: 一个清晰、可读的路由实体名称
2. `route_key`: 一个稳定、简洁、适合程序使用的路由标识
3. `description`: 对该路由实体职责的简洁描述
4. `utterances`: 一组高判别性的用户语料句

## 生成要求
1. `name`
- 应准确表达 skill 的核心用途
- 控制在 4 到 18 个字或对应的简短英文短语

2. `route_key`
- 使用小写字母、数字和点号
- 采用类似 `domain.action` 或 `domain.subdomain.action` 的形式
- 必须稳定、明确、不要使用过于泛化的词，如 `tool`, `misc`, `general`

3. `description`
- 用 1 到 3 句话概括该 skill 解决的问题、主要能力和适用场景
- 要突出和其他通用能力的边界

4. `utterances`
- 生成 10 条高质量语料句
- 语料必须围绕该 skill 的核心能力，具备较强判别性
- 覆盖“关键词/短语”和“简单指令”两种形式
- 不要重复，不要过度泛化，不要输出和 skill 无关的句子

5. 约束
- 如果 skill 信息有限，可以做保守推断，但不要编造明显不存在的能力
- 仅输出结构化结果，不要附加解释

## SKILL.md 内容
{skill_content}

{format_instructions}"""


class Config:
    """应用配置类"""

    # Flask配置
    FLASK_HOST: str = "0.0.0.0"
    FLASK_PORT: int = 5000
    FLASK_DEBUG: bool = False

    # 单工作区数据目录
    DATA_DIR: Path = DATA_DIR

    # Qdrant配置
    QDRANT_URL: str = "http://app.qdrant.free4inno.com"
    QDRANT_COLLECTION: str = ""
    QDRANT_API_KEY: Optional[str] = None
    QDRANT_HEALTH_URL: Optional[str] = None

    # Embedding服务配置
    EMBEDDING_SERVICE_URL: str = "http://embedding.free4inno.com"
    EMBEDDING_MODEL_NAME: str = "Qwen/Qwen3-Embedding-0.6B"  # 仅用于元数据和版本控制
    EMBEDDING_DEVICE: str = "cpu"
    EMBEDDING_HEALTH_URL: Optional[str] = None

    # 可选的只读上游 Agent 数据源
    AGENT_API_URL: Optional[str] = None
    AGENT_API_TOKEN: Optional[str] = None
    AGENT_API_LABEL_IDS: str = ""

    # 默认路由配置
    DEFAULT_ROUTE_ID: int = 0
    DEFAULT_ROUTE_NAME: str = "none"
    DEFAULT_ROUTE_KEY: str = "fallback.default"

    # 性能配置
    BATCH_SIZE: int = 32
    QDRANT_WRITE_BATCH_SIZE: int = 128
    MAX_DELETE_RATIO: float = 0.2

    # 路由配置文件路径
    ROUTES_CONFIG_PATH: str = str(DATA_DIR / "routes.json")
    # 系统设置文件路径
    SETTINGS_FILE_PATH: str = str(DATA_DIR / "settings.json")
    # 诊断缓存文件路径
    DIAGNOSTICS_CACHE_PATH: str = str(DATA_DIR / "diagnostics_cache.json")
    SYNC_TASKS_PATH: str = str(DATA_DIR / "sync_tasks.json")
    SYNC_MAX_ATTEMPTS: int = 5
    QDRANT_TIMEOUT_SECONDS: int = 30

    # 认证配置
    API_KEYS: Optional[str] = None
    AUTH_ENABLED: bool = True

    # Telestar认证配置
    PREDICT_AUTH_KEY: Optional[str] = None

    # 用户配置
    DEFAULT_USERNAME: str = "admin"
    DEFAULT_PASSWORD: str = "123456"

    # LLM配置
    LLM_PROVIDER: str = "deepseek"
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    LLM_MODEL: Optional[str] = None
    LLM_TEMPERATURE: float = 0.7

    # DeepSeek LLM配置（向后兼容）
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: Optional[str] = None
    DEEPSEEK_MODEL: Optional[str] = None

    # 提示词配置
    UTTERANCE_GENERATION_PROMPT: str = ""
    AGENT_REPAIR_PROMPT: str = ""
    SKILL_ROUTE_IMPORT_PROMPT: str = ""

    # 诊断阈值配置
    REGION_THRESHOLD_SIGNIFICANT: float = 0.0
    INSTANCE_THRESHOLD_AMBIGUOUS: float = 0.0

    @classmethod
    def get_settings_path(cls) -> Path:
        """获取设置文件的绝对路径"""
        return Path(cls.SETTINGS_FILE_PATH)

    @classmethod
    def load(cls):
        """从文件加载配置并应用优先级覆盖

        优先级顺序 (由低到高):
        1. 类属性默认值
        2. settings.json (Level 2: 用户真相 SSoT)
        """
        # 1. 从 settings.json 加载 (最高优先级)
        path = cls.get_settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)

        # 若 settings.json 不存在，则创建并写入默认配置（含默认提示词）
        if not path.exists():
            default_settings = cls.to_dict()
            default_settings["UTTERANCE_GENERATION_PROMPT"] = (
                DEFAULT_UTTERANCE_GENERATION_PROMPT
            )
            default_settings["AGENT_REPAIR_PROMPT"] = DEFAULT_AGENT_REPAIR_PROMPT
            default_settings["SKILL_ROUTE_IMPORT_PROMPT"] = DEFAULT_SKILL_ROUTE_IMPORT_PROMPT
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default_settings, f, indent=4, ensure_ascii=False)
                logger.info("已创建 settings.json 并写入默认提示词")
            except Exception as e:
                logger.error(f"创建默认 settings.json 失败: {e}")

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
                    for key, value in settings.items():
                        if hasattr(cls, key) and not key.startswith("_"):
                            setattr(cls, key, value)
            except Exception as e:
                logger.error(f"加载配置文件失败: {e}")

        # 处理向后兼容
        cls._apply_backward_compatibility()
        cls._apply_prompt_defaults()

    @classmethod
    def _apply_backward_compatibility(cls):
        """处理向后兼容性：如果使用deepseek且新配置为空，使用旧配置"""
        if cls.LLM_PROVIDER == "deepseek":
            if cls.LLM_API_KEY is None and cls.DEEPSEEK_API_KEY:
                cls.LLM_API_KEY = cls.DEEPSEEK_API_KEY
            if cls.LLM_BASE_URL is None and cls.DEEPSEEK_BASE_URL:
                cls.LLM_BASE_URL = cls.DEEPSEEK_BASE_URL
            if cls.LLM_MODEL is None and cls.DEEPSEEK_MODEL:
                cls.LLM_MODEL = cls.DEEPSEEK_MODEL

    @classmethod
    def _apply_prompt_defaults(cls):
        """为缺失的提示词应用默认值，兼容旧版 settings.json"""
        if not cls.UTTERANCE_GENERATION_PROMPT:
            cls.UTTERANCE_GENERATION_PROMPT = DEFAULT_UTTERANCE_GENERATION_PROMPT
        if not cls.AGENT_REPAIR_PROMPT:
            cls.AGENT_REPAIR_PROMPT = DEFAULT_AGENT_REPAIR_PROMPT
        if not cls.SKILL_ROUTE_IMPORT_PROMPT:
            cls.SKILL_ROUTE_IMPORT_PROMPT = DEFAULT_SKILL_ROUTE_IMPORT_PROMPT

    @classmethod
    def save(cls, settings_dict: Dict[str, Any]) -> bool:
        """保存配置到文件并更新类属性

        Args:
            settings_dict: 要保存的配置字典

        Returns:
            如果 QDRANT_COLLECTION 发生变化，返回 True；否则返回 False
        """
        # 检测 QDRANT_COLLECTION 是否发生变化
        old_collection = cls.QDRANT_COLLECTION
        collection_changed = False

        # 过滤并更新
        update_data = {}
        for key, value in settings_dict.items():
            if (
                hasattr(cls, key)
                and not key.startswith("_")
                and not callable(getattr(cls, key))
            ):
                # 检测 QDRANT_COLLECTION 变化
                if key == "QDRANT_COLLECTION" and value != old_collection:
                    collection_changed = True
                    logger.info(
                        f"检测到 QDRANT_COLLECTION 变化: {old_collection} -> {value}"
                    )

                setattr(cls, key, value)
                update_data[key] = value

        # 写入文件
        path = cls.get_settings_path()
        try:
            existing_settings = {}
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    existing_settings = json.load(f)

            existing_settings.update(update_data)

            with open(path, "w", encoding="utf-8") as f:
                json.dump(existing_settings, f, indent=4, ensure_ascii=False)
            # 保存后应用向后兼容性
            cls._apply_backward_compatibility()
            cls._apply_prompt_defaults()

        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            raise e

        return collection_changed

    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """获取可供前端配置的项"""
        return {
            # Qdrant配置
            "QDRANT_URL": cls.QDRANT_URL,
            "QDRANT_COLLECTION": cls.QDRANT_COLLECTION,
            "QDRANT_API_KEY": cls.QDRANT_API_KEY,
            "QDRANT_HEALTH_URL": cls.QDRANT_HEALTH_URL,
            # Embedding服务配置
            "EMBEDDING_SERVICE_URL": cls.EMBEDDING_SERVICE_URL,
            "EMBEDDING_MODEL_NAME": cls.EMBEDDING_MODEL_NAME,
            "EMBEDDING_DEVICE": cls.EMBEDDING_DEVICE,
            "EMBEDDING_HEALTH_URL": cls.EMBEDDING_HEALTH_URL,
            "AGENT_API_URL": cls.AGENT_API_URL,
            "AGENT_API_TOKEN": cls.AGENT_API_TOKEN,
            "AGENT_API_LABEL_IDS": cls.AGENT_API_LABEL_IDS,
            # LLM配置（通用）
            "LLM_PROVIDER": cls.LLM_PROVIDER,
            "LLM_API_KEY": cls.LLM_API_KEY,
            "LLM_BASE_URL": cls.LLM_BASE_URL,
            "LLM_MODEL": cls.LLM_MODEL,
            "LLM_TEMPERATURE": cls.LLM_TEMPERATURE,
            # DeepSeek配置（向后兼容）
            "DEEPSEEK_API_KEY": cls.DEEPSEEK_API_KEY,
            "DEEPSEEK_BASE_URL": cls.DEEPSEEK_BASE_URL,
            "DEEPSEEK_MODEL": cls.DEEPSEEK_MODEL,
            # 提示词配置
            "UTTERANCE_GENERATION_PROMPT": cls.UTTERANCE_GENERATION_PROMPT,
            "AGENT_REPAIR_PROMPT": cls.AGENT_REPAIR_PROMPT,
            "SKILL_ROUTE_IMPORT_PROMPT": cls.SKILL_ROUTE_IMPORT_PROMPT,
            # 认证配置
            "AUTH_ENABLED": cls.AUTH_ENABLED,
            "PREDICT_AUTH_KEY": cls.PREDICT_AUTH_KEY,
            "DEFAULT_USERNAME": cls.DEFAULT_USERNAME,
            "DEFAULT_PASSWORD": cls.DEFAULT_PASSWORD,
            # 其他配置
            "BATCH_SIZE": cls.BATCH_SIZE,
            "QDRANT_WRITE_BATCH_SIZE": cls.QDRANT_WRITE_BATCH_SIZE,
            "MAX_DELETE_RATIO": cls.MAX_DELETE_RATIO,
            "DEFAULT_ROUTE_ID": cls.DEFAULT_ROUTE_ID,
            "DEFAULT_ROUTE_NAME": cls.DEFAULT_ROUTE_NAME,
            "DEFAULT_ROUTE_KEY": cls.DEFAULT_ROUTE_KEY,
            # 诊断阈值配置
            "REGION_THRESHOLD_SIGNIFICANT": cls.REGION_THRESHOLD_SIGNIFICANT,
            "INSTANCE_THRESHOLD_AMBIGUOUS": cls.INSTANCE_THRESHOLD_AMBIGUOUS,
        }


# 初始加载（load方法内部已调用_apply_backward_compatibility）
Config.load()
