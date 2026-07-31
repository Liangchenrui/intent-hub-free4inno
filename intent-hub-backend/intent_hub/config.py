"""Runtime configuration persisted in an atomic JSON settings file."""

import json
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_UTTERANCE_GENERATION_PROMPT = """你是意图路由语料专家。根据 Agent 名称 {name}、描述 {description} 和已有正向语料 {reference_utterances}，生成 {count} 条全新、高判别性的用户提问。只输出 JSON 字符串数组。"""
DEFAULT_NEGATIVE_SAMPLE_GENERATION_PROMPT = """你是意图路由语料专家。根据 Agent 名称 {name}、描述 {description}、正向语料 {utterances} 和已有负向语料 {negative_samples}，生成 {count} 条表面相似但明确不属于该 Agent 的负向语料。只输出 JSON 字符串数组。"""
DEFAULT_AGENT_REPAIR_PROMPT = """你是意图路由修复专家。路由 {name_a} 与 {name_b} 存在语义冲突。结合描述、现有语料和冲突样例，返回 JSON：new_utterances、negative_samples、conflicting_utterances、rationalization。只输出 JSON。"""


class Config:
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = False

    DATA_DIR = BACKEND_ROOT / "data"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    AGENTS_FILE = DATA_DIR / "agents.json"
    AGENTS_DB_FILE = DATA_DIR / "agents.db"
    SYNC_STATE_FILE = DATA_DIR / "sync_state.db"
    DIAGNOSTICS_CACHE_FILE = DATA_DIR / "diagnostics_cache.json"
    DEFAULT_ROUTE_FILE = DATA_DIR / "default_route.txt"

    AGENT_API_URL = "https://yuanfang.bupt.edu.cn/ac/api"
    AGENT_API_TOKEN = "0sQe_jpSY-uF2.zKLSz7"

    QDRANT_URL = "http://192.168.33.1:31853"
    QDRANT_API_KEY = "123456"
    QDRANT_COLLECTION = "free4inno_skills"

    EMBEDDING_SERVICE_URL = "http://192.168.33.1:30122"
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    BATCH_SIZE = 32
    QDRANT_WRITE_BATCH_SIZE = 128
    MAX_DELETE_RATIO = 0.2

    SCORE_THRESHOLD = 0.8
    NEGATIVE_THRESHOLD = 0.95
    LLM_PROVIDER = "deepseek"
    LLM_API_KEY: str | None = None
    LLM_BASE_URL: str | None = "https://api.deepseek.com"
    LLM_MODEL: str | None = "deepseek-chat"
    LLM_TEMPERATURE = 0.7
    UTTERANCE_GENERATION_PROMPT = DEFAULT_UTTERANCE_GENERATION_PROMPT
    NEGATIVE_SAMPLE_GENERATION_PROMPT = DEFAULT_NEGATIVE_SAMPLE_GENERATION_PROMPT
    AGENT_REPAIR_PROMPT = DEFAULT_AGENT_REPAIR_PROMPT
    REGION_THRESHOLD_SIGNIFICANT = 0.85
    INSTANCE_THRESHOLD_AMBIGUOUS = 0.92
    AUTH_CODE = "telestar"

    @classmethod
    def load(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if cls.SETTINGS_FILE.exists():
            data = json.loads(cls.SETTINGS_FILE.read_text(encoding="utf-8"))
            for key, value in data.items():
                if key in cls.editable_keys():
                    setattr(cls, key, value)

    @classmethod
    def editable_keys(cls) -> set[str]:
        return {
            "QDRANT_URL", "QDRANT_COLLECTION", "QDRANT_API_KEY",
            "EMBEDDING_SERVICE_URL", "EMBEDDING_MODEL_NAME", "BATCH_SIZE",
            "LLM_PROVIDER", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL",
            "LLM_TEMPERATURE", "UTTERANCE_GENERATION_PROMPT",
            "NEGATIVE_SAMPLE_GENERATION_PROMPT", "AGENT_REPAIR_PROMPT",
            "REGION_THRESHOLD_SIGNIFICANT", "INSTANCE_THRESHOLD_AMBIGUOUS",
        }

    @classmethod
    def to_dict(cls) -> dict[str, Any]:
        return {key: getattr(cls, key) for key in sorted(cls.editable_keys())}

    @classmethod
    def save(cls, values: dict[str, Any]) -> None:
        unknown = set(values) - cls.editable_keys()
        if unknown:
            raise ValueError(f"不支持的设置项: {', '.join(sorted(unknown))}")
        merged = cls.to_dict()
        merged.update(values)
        for required in ("QDRANT_URL", "QDRANT_COLLECTION", "EMBEDDING_SERVICE_URL"):
            if not str(merged.get(required) or "").strip():
                raise ValueError(f"{required} 不能为空")
        merged["BATCH_SIZE"] = int(merged["BATCH_SIZE"])
        if merged["BATCH_SIZE"] <= 0:
            raise ValueError("BATCH_SIZE 必须大于 0")
        for key in ("LLM_TEMPERATURE", "REGION_THRESHOLD_SIGNIFICANT", "INSTANCE_THRESHOLD_AMBIGUOUS"):
            merged[key] = float(merged[key])
        cls.SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        temp = cls.SETTINGS_FILE.with_suffix(".tmp")
        temp.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(cls.SETTINGS_FILE)
        for key, value in merged.items():
            setattr(cls, key, value)

    @classmethod
    def save_collection(cls, collection: str) -> None:
        collection = collection.strip()
        if not collection:
            raise ValueError("QDRANT_COLLECTION 不能为空")
        cls.save({"QDRANT_COLLECTION": collection})


Config.load()
