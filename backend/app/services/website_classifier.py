"""
网站类型识别器
自动分析 URL 和 HTML 结构，识别网站类型并推荐最佳提取器
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple
from urllib.parse import urlparse

logger = __import__('logging').getLogger(__name__)


class WebsiteType(Enum):
    """网站类型枚举"""
    NEWS = "news"           # 新闻/资讯
    GOVERNMENT = "gov"      # 政府/机构
    BLOG = "blog"           # 博客/论坛
    COMMERCE = "ecom"       # 电商/商业
    SOCIAL = "social"       # 社交媒体
    ACADEMIC = "academic"   # 学术/教育
    UNKNOWN = "unknown"


@dataclass
class WebsiteProfile:
    """网站画像"""
    website_type: WebsiteType = WebsiteType.UNKNOWN
    confidence: float = 0.0          # 置信度 0-1
    recommended_extractor: str = ""  # 推荐提取器名称
    hints: List[str] = field(default_factory=list)  # 识别依据
    domain: str = ""                 # 域名


class WebsiteClassifier:
    """网站类型识别器"""

    # URL 模式匹配规则
    URL_PATTERNS = {
        WebsiteType.NEWS: [
            r'news', r'xinwen', r'journal', r'press', r'broadcast',
            r'sina', r'sohu', r'tencent', r'ifeng', r'people',
            r'xinhua', r'cctv', r'163\.com/news', r'thepaper'
        ],
        WebsiteType.GOVERNMENT: [
            r'gov\.cn', r'gov\.', r'org\.cn', r'\.gov\b',
            r'cas\.cn', r'cstnet', r'most\.gov', r'beihang',
            r'tsinghua', r'pku\.edu', r'ustc\.edu',
        ],
        WebsiteType.BLOG: [
            r'blog', r'zhihu', r'juejin', r'csdn', r'cnblogs',
            r'segmentfault', r'v2ex', r'bilibili', r'douban',
        ],
        WebsiteType.COMMERCE: [
            r'shop', r'store', r'mall', r'taobao', r'jd\.com',
            r'alibaba', r'amazon', r'jd\.com', r'pinduoduo',
        ],
        WebsiteType.SOCIAL: [
            r'weibo', r'twitter', r'facebook', r'instagram',
            r'reddit', r'discord', r'tiktok', r'douyin',
        ],
        WebsiteType.ACADEMIC: [
            r'cnki', r'wanfang', r'vip', r'scholar',
            r'arxiv', r'pubmed', r'sciencedirect', r'springer',
        ],
    }

    # HTML 结构特征
    HTML_FEATURES = {
        WebsiteType.NEWS: [
            'article', 'news-content', 'article-content', 'main-content',
            'news-title', 'article-title', 'publish-time', 'source'
        ],
        WebsiteType.GOVERNMENT: [
            'main', 'content', 'article', 'info-list', 'article-title',
            'article-content', 'article-info'
        ],
        WebsiteType.BLOG: [
            'blog-content', 'article-content', 'post-content', 'entry-content',
            'markdown-body', 'article', 'prev-next'
        ],
    }

    # 提取器映射
    EXTRACTOR_MAP = {
        WebsiteType.NEWS: "readability",
        WebsiteType.GOVERNMENT: "density",
        WebsiteType.BLOG: "trafilatura",
        WebsiteType.COMMERCE: "density",
        WebsiteType.SOCIAL: "density",
        WebsiteType.ACADEMIC: "readability",
        WebsiteType.UNKNOWN: "readability",
    }

    def classify(self, url: str, html: str = "") -> WebsiteProfile:
        """
        识别网站类型

        Args:
            url: 网页 URL
            html: 网页 HTML 内容（可选）

        Returns:
            WebsiteProfile: 网站画像
        """
        # 1. 解析域名
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        path = parsed.path.lower()

        profile = WebsiteProfile(domain=domain)
        scores = {t: 0.0 for t in WebsiteType}

        # 2. URL 模式匹配
        url_result = self._classify_by_url(url)
        if url_result:
            scores[url_result] += 0.7
            profile.hints.append(f"URL 匹配: {url_result.value}")

        # 3. HTML 结构分析（如果有 HTML）
        if html:
            html_result = self._classify_by_html(html)
            if html_result:
                scores[html_result] += 0.5
                profile.hints.append(f"HTML 结构匹配: {html_result.value}")

        # 4. 路径特征分析
        path_result = self._classify_by_path(path)
        if path_result:
            scores[path_result] += 0.3
            profile.hints.append(f"路径特征: {path_result.value}")

        # 5. 取最高分类型
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]

        profile.website_type = best_type
        profile.confidence = min(best_score, 1.0)
        profile.recommended_extractor = self.EXTRACTOR_MAP.get(best_type, "readability")

        logger.info(f"网站类型识别: {domain} -> {best_type.value} (置信度: {profile.confidence:.2f})")

        return profile

    def _classify_by_url(self, url: str) -> Optional[WebsiteType]:
        """通过 URL 模式识别"""
        url_lower = url.lower()

        for wtype, patterns in self.URL_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, url_lower):
                    return wtype

        return None

    def _classify_by_path(self, path: str) -> Optional[WebsiteType]:
        """通过 URL 路径识别"""
        # 新闻文章路径特征
        if re.search(r'/\d{4}/|/news/|/article/|/\d{6}/', path):
            return WebsiteType.NEWS

        # 政府网站路径特征
        if re.search(r'/yw/|/zx/|/gk/|/zw/', path):
            return WebsiteType.GOVERNMENT

        # 博客文章路径特征
        if re.search(r'/article/|/post/|/p/|/\d+\.html?', path):
            return WebsiteType.BLOG

        return None

    def _classify_by_html(self, html: str) -> Optional[WebsiteType]:
        """通过 HTML 结构识别"""
        html_lower = html.lower()

        # 计算每个类型特征的出现次数
        scores = {}
        for wtype, features in self.HTML_FEATURES.items():
            count = sum(1 for f in features if f in html_lower)
            scores[wtype] = count

        if scores:
            best = max(scores, key=scores.get)
            if scores[best] >= 2:
                return best

        return None


# 单例实例
classifier = WebsiteClassifier()


def get_website_profile(url: str, html: str = "") -> WebsiteProfile:
    """快捷函数：获取网站画像"""
    return classifier.classify(url, html)