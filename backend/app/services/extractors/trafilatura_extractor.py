"""
Trafilatura 提取器
使用 Trafilatura 库提取网页正文
支持多种格式，通用性强的专业提取库

注意：由于 lxml 版本冲突，此提取器可能不可用
"""

import logging
import re
from typing import Optional

# 延迟导入，避免在 lxml 版本冲突时直接报错
TRAFILATURA_AVAILABLE = False
try:
    import trafilatura
    from trafilatura.metadata import extract_metadata
    TRAFILATURA_AVAILABLE = True
except (ImportError, Exception) as e:
    logger = logging.getLogger(__name__)
    logger.warning(f"Trafilatura 不可用: {e}")

from app.services.extractors.base import BaseExtractor, ExtractedContent
from app.services.website_classifier import WebsiteType

logger = logging.getLogger(__name__)


class TrafilaturaExtractor(BaseExtractor):
    """Trafilatura 提取器"""

    @property
    def name(self) -> str:
        return "trafilatura"

    @property
    def description(self) -> str:
        return "Trafilatura 专业提取库，适合通用场景"

    @property
    def priority(self) -> int:
        return 20  # 中等优先级

    def supports(self, website_type: WebsiteType) -> bool:
        """支持所有类型"""
        return True

    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """使用 Trafilatura 提取正文"""
        if not TRAFILATURA_AVAILABLE:
            logger.warning("Trafilatura 未安装，跳过")
            return ExtractedContent()

        try:
            # 提取正文（返回 XML 格式）
            result = trafilatura.extract(
                html,
                url=url,
                include_comments=False,
                include_images=False,
                include_tables=True,
                output_format="xml",
            )

            if not result:
                logger.info("Trafilatura 未提取到内容")
                return ExtractedContent()

            # 提取元信息
            metadata = extract_metadata(html, url)

            # 提取标题
            title = ""
            if metadata and hasattr(metadata, 'title') and metadata.title:
                title = metadata.title
            else:
                # 尝试从 XML 中提取标题
                import re
                title_match = re.search(r'<title>([^<]+)</title>', result)
                if title_match:
                    title = title_match.group(1)

            # 提取作者
            author = ""
            date_published = ""
            if metadata:
                if hasattr(metadata, 'author') and metadata.author:
                    author = str(metadata.author)
                if hasattr(metadata, 'date') and metadata.date:
                    date_published = str(metadata.date)

            # 清理 XML 标签获取纯文本
            text = self._xml_to_text(result)

            return ExtractedContent(
                title=title,
                content=result,
                text=text,
                author=author,
                published_date=date_published,
                length=len(text),
            )

        except Exception as e:
            logger.warning(f"Trafilatura 提取失败: {e}")
            return ExtractedContent()

    def _xml_to_text(self, xml_content: str) -> str:
        """从 XML 中提取纯文本"""
        import re

        if not xml_content:
            return ""

        # 移除 XML 标签
        text = re.sub(r'<[^>]+>', '', xml_content)

        # 清理空白
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()