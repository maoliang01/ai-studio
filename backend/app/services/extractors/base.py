"""
内容提取器基类
定义提取器接口和通用数据结构
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional

from app.services.website_classifier import WebsiteType


@dataclass
class ExtractedContent:
    """提取的内容"""
    title: str = ""              # 标题
    content: str = ""            # 正文内容（HTML 格式）
    text: str = ""               # 纯文本内容
    html: str = ""               # 原始 HTML
    author: str = ""             # 作者
    published_date: str = ""     # 发布日期
    source: str = ""             # 来源
    keywords: List[str] = field(default_factory=list)  # 关键词
    language: str = ""           # 语言
    length: int = 0              # 字符数

    def is_valid(self) -> bool:
        """检查提取结果是否有效"""
        return len(self.text) > 100  # 至少 100 个字符

    def get_clean_text(self) -> str:
        """获取清洗后的纯文本"""
        return self.text.strip() if self.text else self.content


class BaseExtractor(ABC):
    """内容提取器基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """提取器名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """提取器描述"""
        pass

    @property
    def priority(self) -> int:
        """优先级，数字越小越优先"""
        return 50

    @abstractmethod
    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """
        从 HTML 中提取内容

        Args:
            html: 网页 HTML 内容
            url: 网页 URL（用于参考）

        Returns:
            ExtractedContent: 提取的内容
        """
        pass

    @abstractmethod
    def supports(self, website_type: WebsiteType) -> bool:
        """
        是否支持该网站类型

        Args:
            website_type: 网站类型

        Returns:
            bool: 是否支持
        """
        pass

    def extract_from_markdown(self, markdown: str, url: str = "") -> ExtractedContent:
        """
        从 Markdown 中提取内容（备用方法）

        Args:
            markdown: Markdown 内容
            url: 网页 URL

        Returns:
            ExtractedContent: 提取的内容
        """
        return ExtractedContent(text=markdown, content=markdown, length=len(markdown))