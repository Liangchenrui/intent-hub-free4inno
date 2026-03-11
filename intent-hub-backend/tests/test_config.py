"""配置模块测试"""
from intent_hub.config import Config


def test_config_defaults():
    """测试配置默认值"""
    assert Config.DEFAULT_ROUTE_ID == 0
    assert Config.DEFAULT_ROUTE_NAME == "none"
    assert Config.BATCH_SIZE == 32

