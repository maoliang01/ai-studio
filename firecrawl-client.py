"""
Firecrawl API 客户端
用于本地部署的 Firecrawl 服务调用
"""
import httpx
import json
from typing import Optional, List, Dict, Any

# 默认配置
DEFAULT_BASE_URL = "http://localhost:3002"
DEFAULT_API_KEY = "local"  # 本地部署不需要真正的 API key


class FirecrawlClient:
    """Firecrawl API 客户端"""

    def __init__(
        self,
        api_key: str = DEFAULT_API_KEY,
        base_url: str = DEFAULT_BASE_URL
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """发送请求"""
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.request(method, url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()

    def scrape(
        self,
        url: str,
        formats: Optional[List[str]] = None,
        headers: Optional[Dict] = None,
        locate: bool = True
    ) -> Dict[str, Any]:
        """
        抓取单个网页

        Args:
            url: 目标 URL
            formats: 返回格式列表 ["markdown", "html", "links", "screenshot"]
            headers: 自定义请求头
            locate: 是否返回内容位置信息

        Returns:
            抓取结果
        """
        if formats is None:
            formats = ["markdown"]

        data = {
            "url": url,
            "formats": formats,
            "locate": locate
        }
        if headers:
            data["headers"] = headers

        return self._request("POST", "/v1/scrape", data)

    def crawl(
        self,
        url: str,
        search: Optional[str] = None,
        limit: int = 10,
        formats: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        递归爬取网站

        Args:
            url: 起始 URL
            search: 搜索关键词（可选）
            limit: 最大页面数
            formats: 返回格式

        Returns:
            爬取任务 ID 和状态
        """
        if formats is None:
            formats = ["markdown"]

        data = {
            "url": url,
            "search": search,
            "limit": limit,
            "formats": formats,
            "crawlType": "dynamic"  # 或 "static"
        }

        return self._request("POST", "/v1/crawl", data)


class LocalFirecrawlAPI:
    """本地 Firecrawl API 配置管理"""

    @staticmethod
    def check_status() -> bool:
        """检查服务是否运行"""
        try:
            with httpx.Client() as client:
                response = client.get(f"{DEFAULT_BASE_URL}/health", timeout=5.0)
                return response.status_code == 200
        except Exception:
            return False

    @staticmethod
    def get_status_info() -> Dict[str, Any]:
        """获取状态信息"""
        status = {
            "service_running": LocalFirecrawlAPI.check_status(),
            "api_url": DEFAULT_BASE_URL,
            "docs_url": f"{DEFAULT_BASE_URL}/docs"
        }
        return status


# ===== 使用示例 =====

if __name__ == "__main__":
    print("=" * 50)
    print("Firecrawl 本地 API 测试")
    print("=" * 50)

    # 检查服务状态
    print("\n[1] 检查服务状态...")
    info = LocalFirecrawlAPI.get_status_info()
    print(f"    服务运行中: {info['service_running']}")
    print(f"    API 地址: {info['api_url']}")
    print(f"    文档地址: {info['docs_url']}")

    if not info["service_running"]:
        print("\n❌ 服务未运行，请先启动 Firecrawl:")
        print("    1. 打开终端")
        print("    2. 运行: cd /tmp/firecrawl && sudo docker compose up -d")
        print("    3. 等待服务启动（约10秒）")
        exit(1)

    # 测试爬取
    print("\n[2] 测试抓取网页...")
    client = FirecrawlClient()

    try:
        result = client.scrape(
            url="https://example.com",
            formats=["markdown"]
        )

        print(f"    ✅ 抓取成功!")
        print(f"    标题: {result.get('metadata', {}).get('title', 'N/A')}")

        # 显示部分内容预览
        content = result.get('data', {}).get('markdown', '')
        if content:
            preview = content[:300].replace('\n', ' ')
            print(f"    内容预览: {preview}...")

    except Exception as e:
        print(f"    ❌ 抓取失败: {e}")

    print("\n" + "=" * 50)
    print("测试完成!")
    print("=" * 50)