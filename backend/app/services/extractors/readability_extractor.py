"""
Readability 算法提取器
使用 Mozilla Readability 算法提取网页正文
适合新闻、资讯、博客等内容为主的网站
"""

import re
import logging
from typing import Optional

from readability import Document
from bs4 import BeautifulSoup

from app.services.extractors.base import BaseExtractor, ExtractedContent
from app.services.website_classifier import WebsiteType

logger = logging.getLogger(__name__)


class ReadabilityExtractor(BaseExtractor):
    """Readability 算法提取器"""

    @property
    def name(self) -> str:
        return "readability"

    @property
    def description(self) -> str:
        return "Mozilla Readability 算法，适合新闻/资讯类网站"

    @property
    def priority(self) -> int:
        return 10  # 高优先级，新闻类网站首选

    def supports(self, website_type: WebsiteType) -> bool:
        """支持新闻、学术类网站"""
        return website_type in [
            WebsiteType.NEWS,
            WebsiteType.ACADEMIC,
            WebsiteType.BLOG,
            WebsiteType.UNKNOWN,  # 未知类型默认使用
        ]

    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """使用 Readability 提取正文"""
        try:
            doc = Document(html)

            # 提取标题
            title = doc.title() or ""

            # 提取正文（HTML 格式）
            content_html = doc.summary() or ""

            # 转换为纯文本
            text = self._html_to_text(content_html)

            # 如果 Readability 提取的正文太短，尝试从 meta description 获取
            if len(text) < 200:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html, 'lxml')
                meta_desc = soup.find('meta', attrs={'name': 'description'})
                if meta_desc and meta_desc.get('content'):
                    description = meta_desc['content'].strip()
                    if len(description) > 50:
                        text = description
                        content_html = description

            return ExtractedContent(
                title=title,
                content=content_html,
                text=text,
                length=len(text),
            )

        except Exception as e:
            logger.warning(f"Readability 提取失败: {e}")
            return ExtractedContent()

    def _html_to_text(self, html: str) -> str:
        """HTML 转纯文本"""
        if not html:
            return ""

        soup = BeautifulSoup(html, 'lxml')

        # 移除脚本和样式
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()

        # 获取文本
        text = soup.get_text(separator='\n', strip=True)

        # 清理多余空行
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()