"""BUPT's settings surface, backed by the same effective configuration."""
from intent_hub.config import Config

KEYS = {
    'QDRANT_URL', 'QDRANT_COLLECTION', 'EMBEDDING_SERVICE_URL', 'EMBEDDING_MODEL_NAME',
    'BATCH_SIZE', 'LLM_PROVIDER', 'LLM_BASE_URL', 'LLM_MODEL', 'LLM_TEMPERATURE',
    'UTTERANCE_GENERATION_PROMPT', 'LLM_FALLBACK_ENABLED', 'LLM_FALLBACK_TOP_K',
    'LLM_FALLBACK_TIMEOUT_SECONDS', 'NEGATIVE_SAMPLE_GENERATION_PROMPT',
    'AGENT_REPAIR_PROMPT', 'REGION_THRESHOLD_SIGNIFICANT', 'INSTANCE_THRESHOLD_AMBIGUOUS',
}


def settings():
    return {key: getattr(Config, key) for key in sorted(KEYS)}


def save(values):
    unknown = set(values) - KEYS
    if unknown:
        raise ValueError('不支持的设置项: ' + ', '.join(sorted(unknown)))
    merged = {**settings(), **values}
    for required in ('QDRANT_URL', 'QDRANT_COLLECTION', 'EMBEDDING_SERVICE_URL'):
        if not str(merged.get(required) or '').strip():
            raise ValueError(required + ' 不能为空')
    merged['BATCH_SIZE'] = int(merged['BATCH_SIZE'])
    if merged['BATCH_SIZE'] <= 0:
        raise ValueError('BATCH_SIZE 必须大于 0')
    for key in ('LLM_TEMPERATURE', 'REGION_THRESHOLD_SIGNIFICANT', 'INSTANCE_THRESHOLD_AMBIGUOUS'):
        merged[key] = float(merged[key])
    Config.save(merged)
