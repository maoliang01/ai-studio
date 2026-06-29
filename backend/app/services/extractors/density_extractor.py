"""
内容密度提取器
基于启发式算法，分析 HTML 块的文本密度和链接密度来识别正文区域
适合政府、企业、复杂布局的网站
"""

import re
import logging
from typing import List, Optional, Tuple
from dataclasses import dataclass

from bs4 import BeautifulSoup, Tag

from app.services.extractors.base import BaseExtractor, ExtractedContent
from app.services.website_classifier import WebsiteType

logger = logging.getLogger(__name__)


@dataclass
class ContentBlock:
    """内容区块"""
    element: Tag
    text_content: str
    link_text_length: int
    tag_score: int  # 标签权重
    density_score: float

    @property
    def link_density(self) -> float:
        """链接密度：链接文字占总文字的比例"""
        if not self.text_content:
            return 1.0
        return min(self.link_text_length / len(self.text_content), 1.0)

    @property
    def length(self) -> int:
        return len(self.text_content)

    @property
    def final_score(self) -> float:
        """最终得分：文本密度高 + 链接密度低 + 标签权重"""
        text_density = 1 - self.link_density
        return (text_density * self.length + self.tag_score * 10) / (self.length / 100 + 1)


class DensityExtractor(BaseExtractor):
    """内容密度提取器"""

    # 噪音标签（完全删除）
    NOISE_TAGS = ['script', 'style', 'noscript', 'iframe', 'form', 'button',
                  'nav', 'footer', 'header', 'aside', 'meta', 'link']

    # 噪音 class/id（删除元素）
    NOISE_SELECTORS = [
        'nav', 'menu', 'sidebar', 'footer', 'header', 'comment',
        'social', 'share', 'ad', 'advertisement', 'breadcrumb', 'sidebar',
        'related', 'recommend', 'hot', 'rank', 'toolbar', 'navbar',
        'nav-menu', 'nav-header', 'footer-content', 'copyright',
        'address', 'time', 'datetime',  # 时间元素通常是元信息
    ]

    # 内容标签权重
    CONTENT_TAGS = {
        'article': 25,
        'main': 25,
        'section': 15,
        'div': 5,
        'td': 10,
        'p': 15,
    }

    @property
    def name(self) -> str:
        return "density"

    @property
    def description(self) -> str:
        return "内容密度算法，适合政府/企业/复杂布局网站"

    @property
    def priority(self) -> int:
        return 30  # 第二优先级

    def supports(self, website_type: WebsiteType) -> bool:
        """支持所有类型，但用于政府/企业网站时优先级更高"""
        return True  # 所有类型都支持，作为备选

    def extract(self, html: str, url: str = "") -> ExtractedContent:
        """基于内容密度提取正文"""
        try:
            soup = BeautifulSoup(html, 'lxml')

            # 1. 移除噪音元素
            self._remove_noise_elements(soup)

            # 2. 分割并评分所有候选块
            blocks = self._score_all_blocks(soup)

            if not blocks:
                logger.warning("未找到任何内容块")
                return ExtractedContent()

            # 3. 选择得分最高的块
            best_blocks = self._select_best_blocks(blocks)

            # 4. 提取内容
            content = self._extract_from_blocks(best_blocks)

            # 5. 尝试提取标题
            title = self._extract_title(soup)

            return ExtractedContent(
                title=title,
                content=content,
                text=self._clean_text(content),
                length=len(content),
            )

        except Exception as e:
            logger.error(f"Density 提取失败: {e}")
            return ExtractedContent()

    def _remove_noise_elements(self, soup: BeautifulSoup) -> None:
        """移除噪音元素"""
        # 移除噪音标签
        for tag_name in self.NOISE_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # 移除噪音选择器
        for selector in self.NOISE_SELECTORS:
            for element in soup.find_all(class_=re.compile(selector, re.I)):
                element.decompose()
            for element in soup.find_all(id=re.compile(selector, re.I)):
                element.decompose()

    def _score_all_blocks(self, soup: BeautifulSoup) -> List[ContentBlock]:
        """对所有候选块评分"""
        blocks = []

        # 遍历主要容器标签
        for tag_name in ['article', 'main', 'section', 'div', 'td']:
            for element in soup.find_all(tag_name):
                block = self._score_block(element)
                if block and block.length > 200:  # 至少 200 字符
                    blocks.append(block)

        # 按得分排序
        blocks.sort(key=lambda x: x.final_score, reverse=True)

        return blocks

    def _score_block(self, element: Tag) -> Optional[ContentBlock]:
        """对单个块评分"""
        # 获取文本内容
        text = element.get_text(separator=' ', strip=True)

        if not text or len(text) < 100:
            return None

        # 计算链接文字长度
        link_text = ""
        for a in element.find_all('a'):
            link_text += a.get_text(strip=True)

        # 标签权重
        tag_name = element.name.lower()
        tag_score = self.CONTENT_TAGS.get(tag_name, 1)

        # 内容密度分数
        link_length = len(link_text)
        text_length = len(text)
        if text_length > 0:
            density = (text_length - link_length) / text_length
        else:
            density = 0

        return ContentBlock(
            element=element,
            text_content=text,
            link_text_length=link_length,
            tag_score=tag_score,
            density_score=density,
        )

    def _select_best_blocks(self, blocks: List[ContentBlock], top_n: int = 5) -> List[ContentBlock]:
        """选择最佳内容块"""
        if not blocks:
            return []

        # 取前 N 个块
        selected = blocks[:top_n]

        # 检查是否有嵌套关系，去除被包含的块
        result = []
        for block in selected:
            is_duplicate = False
            for existing in result:
                # 如果当前块被已有块包含，跳过
                if block.element in existing.element:
                    is_duplicate = True
                    break
            if not is_duplicate:
                result.append(block)

        return result[:1]  # 只选择 1 个最佳块，避免重复

    def _extract_from_blocks(self, blocks: List[ContentBlock]) -> str:
        """从选中的块中提取内容"""
        contents = []

        for block in blocks:
            # 提取段落文本
            paragraphs = []
            for p in block.element.find_all('p'):
                text = p.get_text(strip=True)
                if len(text) > 50:  # 只保留长度足够的段落
                    paragraphs.append(text)

            if paragraphs:
                contents.append('\n\n'.join(paragraphs))

        return '\n\n---\n\n'.join(contents) if contents else blocks[0].text_content if blocks else ""

    def _extract_title(self, soup: BeautifulSoup) -> str:
        """提取标题"""
        # 尝试从 h1 获取
        h1 = soup.find('h1')
        if h1:
            return h1.get_text(strip=True)

        # 尝试从 title 获取
        title = soup.find('title')
        if title:
            return title.get_text(strip=True)

        # 尝试 meta
        meta_title = soup.find('meta', attrs={'name': 'title'})
        if meta_title:
            return meta_title.get('content', '')

        return ""

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        if not text:
            return ""

        # 清理空白
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # 清理残留的导航项（通用规则）
        nav_items = [
            '首页', '组织机构', '科学研究', '成果转化', '人才教育', '科学普及',
            '党建', '信息公开', '联系我们', '网站地图', '发表于', '作者：',
            '来源：', '责任编辑', '点击量', '浏览次数', '分享', '收藏',
        ]

        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            # 跳过空行和短导航行
            if not stripped or len(stripped) < 5:
                continue
            # 跳过以导航词开头的短行
            if any(stripped.startswith(n) for n in nav_items if len(n) > 2):
                if len(stripped) < 50:
                    continue
            cleaned_lines.append(stripped)

        return '\n'.join(cleaned_lines).strip()