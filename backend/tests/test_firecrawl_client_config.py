"""
Firecrawl 客户端配置检测单元测试

背景：项目部署时如果没配 FIRECRAWL_API_KEY，也没启用本地 Firecrawl 服务，
Firecrawl 客户端每次 scrape_url 都会发请求到 https://api.firecrawl.dev/v0/scrape
然后 401 失败。每个请求白白浪费 1-2 秒。

测试覆盖 `FirecrawlClient.is_configured()` 方法：
1. 无 api_key + 非 use_local → False（应短路）
2. 有 api_key + 非 use_local → True
3. use_local=True → True（本地服务不需要 key）
4. use_local=True 但 local_url 是 LOCAL_BASE_URL（默认） → True（按配置意图）
"""

import os
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app.services.scraper import FirecrawlClient  # noqa: E402


class TestFirecrawlClientIsConfigured(unittest.TestCase):
    def test_no_api_key_no_local_returns_false(self):
        """既无 API key 又非本地模式 → 未配置"""
        with patch.dict(os.environ, {}, clear=True):
            # 显式清空 FIRECRAWL_API_KEY
            os.environ.pop("FIRECRAWL_API_KEY", None)
            client = FirecrawlClient(api_key="", use_local=False)
            self.assertFalse(client.is_configured(),
                             "无 API key 且非本地模式时，Firecrawl 不可用")

    def test_with_api_key_returns_true(self):
        """有 API key → 已配置"""
        client = FirecrawlClient(api_key="fc-test-key", use_local=False)
        self.assertTrue(client.is_configured(),
                        "有 API key 时，Firecrawl 应可用")

    def test_use_local_returns_true(self):
        """use_local=True → 不需要 API key，本地服务视为已配置"""
        client = FirecrawlClient(api_key="", use_local=True, local_url="http://localhost:3002")
        self.assertTrue(client.is_configured(),
                        "use_local=True 时，Firecrawl 应视为已配置")

    def test_api_key_from_env_returns_true(self):
        """从环境变量 FIRECRAWL_API_KEY 读取时也应识别为已配置"""
        with patch.dict(os.environ, {"FIRECRAWL_API_KEY": "fc-env-key"}):
            client = FirecrawlClient(use_local=False)
            self.assertTrue(client.is_configured(),
                            "环境变量设置了 API key 时，Firecrawl 应可用")


if __name__ == "__main__":
    unittest.main()
