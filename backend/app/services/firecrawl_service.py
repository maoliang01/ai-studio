"""
Firecrawl 服务封装
用于替代或补充 crawl4ai 的网页爬取功能
"""

import logging
from typing import Optional, List
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)

# Firecrawl 服务地址
FIRECRAWL_URL = "http://localhost:3002"


@dataclass
class FirecrawlResult:
    """Firecrawl 爬取结果"""
    url: str
    title: str = ""
    content: str = ""
    html: str = ""
    word_count: int = 0
    links: List[str] = field(default_factory=list)
    status: str = "pending"
    error_message: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FirecrawlService:
    """Firecrawl 服务封装类"""

    def __init__(self, api_url: str = FIRECRAWL_URL):
        self.api_url = api_url.rstrip('/')
        self._client = None

    def _get_client(self):
        """获取 Firecrawl 客户端"""
        if self._client is None:
            try:
                from firecrawl import Firecrawl
                self._client = Firecrawl(
                    api_key="",  # 本地部署不需要 API Key
                    api_url=self.api_url
                )
                logger.info(f"Firecrawl 客户端初始化成功: {self.api_url}")
            except ImportError:
                logger.error("Firecrawl SDK 未安装，请运行: pip install firecrawl-py")
                raise ImportError("请安装 firecrawl-py: pip install firecrawl-py")
        return self._client

    def scrape(self, url: str, formats: Optional[List[str]] = None) -> FirecrawlResult:
        """
        抓取单个网页

        Args:
            url: 网页 URL
            formats: 输出格式，默认 ["markdown", "html", "links"]

        Returns:
            FirecrawlResult: 爬取结果
        """
        if formats is None:
            formats = ["markdown", "html"]

        result = FirecrawlResult(url=url)

        try:
            client = self._get_client()
            logger.info(f"Firecrawl 开始抓取: {url}")

            response = client.scrape(url, formats=formats)

            # 处理不同的响应格式
            # 1. 直接属性格式 (SDK 返回的)
            # 2. 嵌套 data 格式 (API 直接返回的)
            data = response

            # 如果有 data 嵌套
            if hasattr(response, 'data') and response.data:
                data = response.data
            elif isinstance(response, dict) and 'data' in response:
                data = response['data']

            # 提取标题
            if hasattr(data, 'metadata') and data.metadata:
                metadata = data.metadata
                if isinstance(metadata, dict):
                    result.title = metadata.get('title', '') or ''
                else:
                    result.title = getattr(metadata, 'title', '') or ''
            elif isinstance(data, dict):
                result.title = data.get('metadata', {}).get('title', '') or ''

            # 提取正文
            content = ""
            if hasattr(data, 'markdown') and data.markdown:
                content = data.markdown
            elif hasattr(data, 'content') and data.content:
                content = data.content
            elif isinstance(data, dict):
                content = data.get('markdown') or data.get('content') or ""

            result.content = content
            result.word_count = len(content.replace('\n', '').replace(' ', ''))

            # 提取 HTML
            if hasattr(data, 'html') and data.html:
                result.html = data.html
            elif isinstance(data, dict):
                result.html = data.get('html', '')

            # 提取链接
            if hasattr(data, 'links') and data.links:
                result.links = data.links
            elif hasattr(data, 'linksOnPage') and data.linksOnPage:
                result.links = data.linksOnPage
            elif isinstance(data, dict):
                result.links = data.get('links') or data.get('linksOnPage', []) or []

            result.status = "success"
            logger.info(f"Firecrawl 抓取成功: {url}, 字数: {result.word_count}")

        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            logger.error(f"Firecrawl 抓取失败: {url}, 错误: {e}")

        return result

    def map(self, url: str) -> dict:
        """
        获取网站地图

        Args:
            url: 网站 URL

        Returns:
            dict: {"links": [...], "metadata": {...}}
        """
        try:
            client = self._get_client()
            logger.info(f"Firecrawl 获取网站地图: {url}")

            response = client.map(url)

            return {
                "links": response.links if hasattr(response, 'links') else [],
                "metadata": {
                    "title": getattr(response, 'metadata', {}).get('title', '') if hasattr(response, 'metadata') else '',
                    "description": getattr(response, 'metadata', {}).get('description', '') if hasattr(response, 'metadata') else '',
                },
                "status": "success"
            }

        except Exception as e:
            logger.error(f"Firecrawl 地图获取失败: {url}, 错误: {e}")
            return {
                "links": [],
                "metadata": {},
                "status": "error",
                "error_message": str(e)
            }

    def is_available(self) -> bool:
        """检查 Firecrawl 服务是否可用"""
        try:
            import httpx
            response = httpx.get(f"{self.api_url}/", timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Firecrawl 服务不可用: {e}")
            return False


# 全局单例
_firecrawl_service: Optional[FirecrawlService] = None


def get_firecrawl_service() -> FirecrawlService:
    """获取全局 Firecrawl 服务实例"""
    global _firecrawl_service
    if _firecrawl_service is None:
        _firecrawl_service = FirecrawlService()
    return _firecrawl_service