"""Fixed infrastructure configuration with one writable collection setting."""

import json
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Config:
    FLASK_HOST = "0.0.0.0"
    FLASK_PORT = 5000
    FLASK_DEBUG = False

    DATA_DIR = BACKEND_ROOT / "data"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    AGENTS_FILE = DATA_DIR / "agents.json"
    DEFAULT_ROUTE_FILE = DATA_DIR / "default_route.txt"

    AGENT_API_URL = "https://yuanfang.bupt.edu.cn/ac/api"
    AGENT_API_TOKEN = "0sQe_jpSY-uF2.zKLSz7"

    QDRANT_URL = "http://192.168.33.1:31853"
    QDRANT_API_KEY = "123456"
    QDRANT_COLLECTION = "free4inno_skills"

    EMBEDDING_SERVICE_URL = "http://192.168.33.1:30122"
    EMBEDDING_MODEL_NAME = "BAAI/bge-m3"
    BATCH_SIZE = 32

    SCORE_THRESHOLD = 0.8
    NEGATIVE_THRESHOLD = 0.95
    DEFAULT_USERNAME = "admin"
    DEFAULT_PASSWORD = "123456"

    @classmethod
    def load(cls) -> None:
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if cls.SETTINGS_FILE.exists():
            data = json.loads(cls.SETTINGS_FILE.read_text(encoding="utf-8"))
            collection = str(data.get("QDRANT_COLLECTION", "")).strip()
            if collection:
                cls.QDRANT_COLLECTION = collection

    @classmethod
    def save_collection(cls, collection: str) -> None:
        collection = collection.strip()
        if not collection:
            raise ValueError("QDRANT_COLLECTION 不能为空")
        cls.QDRANT_COLLECTION = collection
        cls.SETTINGS_FILE.write_text(
            json.dumps({"QDRANT_COLLECTION": collection}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


Config.load()

