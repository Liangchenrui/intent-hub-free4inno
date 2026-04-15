"""配置模块测试"""
from intent_hub.config import Config


def test_config_defaults():
    """测试配置默认值"""
    assert Config.DEFAULT_ROUTE_ID == 0
    assert Config.DEFAULT_ROUTE_NAME == "none"
    assert Config.DEFAULT_ROUTE_KEY == "fallback.default"
    assert Config.BATCH_SIZE == 32
    assert Config.DEFAULT_TENANT_ID == "default"
    assert Config.PLATFORM_DATA_DIR == Config.DATA_DIR / "platform"
    assert Config.TENANTS_DATA_DIR == Config.DATA_DIR / "tenants"
