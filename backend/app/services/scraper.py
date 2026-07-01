"""
网页爬取服务
使用 Firecrawl 爬取 + URL 日期提取 + LLM 摘要

核心特点：
1. 日期提取：URL 日期优先，严格验证
2. 爬取：Firecrawl（支持 JS 渲染）
3. 摘要：大模型辅助提取
"""

import asyncio
import json
import logging
import re
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta


def extract_date_from_content(content: str, base_url: str = "") -> Tuple[Optional[str], Optional[str]]:
    """
    从文章内容中提取发布日期

    Returns:
        Tuple[str, Optional[str]]: (published_at, author)
        例如: ("2026-06-23", "张三")
    """
    if not content:
        return None, None

    lines = [l.strip() for l in content.split('\n') if l.strip()]

    # 日期和作者提取模式（中文网站常用格式）
    # 模式1: "来源：光明日报 作者：张三 2026-06-24"
    # 模式2: "发布时间：2026-06-23  作者：李四"
    # 模式3: "发布日期：2026年6月23日"
    # 模式4: "2026-06-23 作者：王五"

    date_patterns = [
        # YYYY-MM-DD 格式
        r'(\d{4}-\d{2}-\d{2})',
        # YYYY/MM/DD 格式
        r'(\d{4}/\d{2}/\d{2})',
        # 中文格式：YYYY年MM月DD日
        r'(\d{4}年\d{1,2}月\d{1,2}日)',
    ]

    author_patterns = [
        # "作者：张三" 或 "作者:张三"
        r'作者[：:]\s*([^\s\d]+)',
        # "文/张三" 或 "文：张三"
        r'文[／/][图]?\s*([^\s\d]+)',
        # "摄影：张三"
        r'摄影[：:]\s*([^\s\d]+)',
    ]

    published_at = None
    author = None

    # 在前20行中搜索日期和作者（通常在文章开头）
    search_range = min(20, len(lines))
    for i, line in enumerate(lines[:search_range]):
        # 提取日期
        if published_at is None:
            for pattern in date_patterns:
                match = re.search(pattern, line)
                if match:
                    date_str = match.group(1)
                    # 转换为标准格式
                    if '-' in date_str:
                        normalized = date_str
                    elif '/' in date_str:
                        normalized = date_str.replace('/', '-')
                    else:
                        # 中文格式
                        normalized = date_str.replace('年', '-').replace('月', '-').replace('日', '')
                    # 验证日期
                    try:
                        parsed = datetime.strptime(normalized, "%Y-%m-%d")
                        d = parsed.date()
                        if d.year >= 2000 and d <= date.today() + timedelta(days=1):
                            published_at = normalized
                            break
                    except:
                        pass

        # 提取作者
        if author is None:
            for pattern in author_patterns:
                match = re.search(pattern, line)
                if match:
                    author = match.group(1).strip()
                    break

        if published_at and author:
            break

    return published_at, author
from urllib.parse import urlparse, urljoin
import httpx

logger = logging.getLogger(__name__)

# ================================================
# 内容清理工具
# ================================================

def clean_content(content: str) -> str:
    """
    清理文章内容，去除无语义符号和导航元素

    清理规则：
    1. 去除 Markdown 图片链接: ![alt](url) -> 空
    2. 去除 Markdown 链接: [text](url) -> text
    3. 去除纯链接行: http://xxx.com -> 空
    4. 去除 javascript:void(0) 等无意义链接
    5. 去除零宽字符和不可见字符
    6. 去除网站导航元素（ENGLISH、网站地图、当前位置等）
    7. 规范化空白字符
    """
    if not content:
        return content

    # 1. 去除 Markdown 图片链接: ![alt](url) -> 空
    content = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', content)

    # 2. 去除空图片链接行: [](url) -> 空
    content = re.sub(r'^\[\]\([^)]+\)\s*$', '', content, flags=re.MULTILINE)

    # 3. 去除空括号行: [] 或 []()
    content = re.sub(r'^\[\]\s*$', '', content, flags=re.MULTILINE)

    # 4. 去除 Markdown 链接，保留文字: [text](url) -> text
    content = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', content)

    # 5. 清理残留的空链接: []( 或 [])
    content = re.sub(r'\[\]$', '', content)
    content = re.sub(r'\[\]\([^)]*\)$', '', content, flags=re.MULTILINE)

    # 6. 去除纯URL链接行
    content = re.sub(r'^https?://[^\s]+$', '', content, flags=re.MULTILINE)

    # 7. 清理所有剩余的空链接格式: [](...) 或 []
    content = re.sub(r'\[\]', '', content)
    content = re.sub(r'\[\]\([^)]*\)', '', content)

    # 8. 去除 javascript:void(0) 和类似的无意义链接
    content = re.sub(r'javascript:void\s*\(0\)', '', content)
    content = re.sub(r'javascript:;', '', content)

    # 9. 去除零宽字符
    zero_width_chars = [
        '​', '‌', '‍', '﻿', '­', '᠎', '​', '‌', '‍', '﻿'
    ]
    for char in zero_width_chars:
        content = content.replace(char, '')

    # 10. 去除控制字符（保留换行和回车）
    content = ''.join(char for char in content if ord(char) >= 32 or char in '\n\r\t')

    # 11. 规范化空白字符
    content = re.sub(r'[ \t]+', ' ', content)
    content = re.sub(r'\n{3,}', '\n\n', content)

    # 12. 去除行首行尾空白，移除空行
    lines = [line.strip() for line in content.split('\n')]
    content = '\n'.join(line for line in lines if line)

    # 13. 最终清理：移除孤立的空括号
    content = re.sub(r'^\s*\(\)\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^\s*\(\s*\)\s*$', '', content, flags=re.MULTILINE)

    # 14. 去除开头的导航菜单元素（1. ENGLISH 2. 网站地图 等）
    # 匹配类似 "1. ENGLISH\n2. 网站地图\n..." 的模式
    nav_pattern = r'^(?:\d+\.\s*(?:ENGLISH|网站地图|中国科学院|邮箱登录|联系我们)[\s\n]*)+'
    content = re.sub(nav_pattern, '', content, flags=re.IGNORECASE)

    # 15. 去除"当前位置"导航行和栏目导航
    content = re.sub(r'^当前位置[：:]?\s*>>?\s*首页\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^>>\s*首页\s*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^>>\s*[一-龥A-Za-z]+(?:\s*>>\s*[一-龥A-Za-z]+)*\s*$', '', content, flags=re.MULTILINE)  # >> 栏目名

    # 16. 去除顶部的栏目名（单独一行的"工作动态"、"党群园地"等）
    content = re.sub(r'^(?:工作动态|党群园地|首页|科普园地|组织机构|新闻中心)[^\n]*\n?', '', content, flags=re.MULTILINE)

    # 17. 去除分隔线（----、====、****）
    content = re.sub(r'^[-=*]{3,}\s*$', '', content, flags=re.MULTILINE)

    # 18. 去除底部的版权和备案信息
    footer_patterns = [
        r'版权所有\s*[©©]\s*[^\n]+',
        r'备案序号[：:]\s*[^\n]+',
        r'京ICP备\d+号[^\n]*',
        r'京公网安备\d+号[^\n]*',
        r'地址[：:]\s*[^\n]+',
        r'邮编[：:]\s*\d+[^\n]*',
    ]
    for pattern in footer_patterns:
        content = re.sub(pattern, '', content)

    # 19. 去除底部"版权所有"等整行
    content = re.sub(r'^[^\n]*版权所有[^\n]*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^[^\n]*备案序号[^\n]*$', '', content, flags=re.MULTILINE)
    content = re.sub(r'^[^\n]*京ICP备[^\n]*$', '', content, flags=re.MULTILINE)

    # 20. 再清理"加载更多"等按钮文字
    content = re.sub(r'^加载更多[^\n]*$', '', content, flags=re.MULTILINE)

    # 21. 去除网站导航元素（手机版、PC版本、网站无障碍等）
    nav_element_patterns = [
        r'^手机版\s*$',
        r'^PC版本\s*$',
        r'^网站无障碍\)\s*$',
        r'^学习进行时\s*$',
        r'^多语种频道\s*$',
        r'^地方频道\s*$',
        r'^网站地图\s*$',
    ]
    for pattern in nav_element_patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE)

    # 22. 去除栏目列表导航（如：* 高层、* 时政、* 人事 等 Markdown 列表格式）
    # 先处理列表项格式，再处理纯文字格式
    category_list_patterns = [
        # Markdown 列表格式: * 高层
        r'^\*\s*(?:学习进行时|高层|时政|人事|国际|财经|网评|港澳|台湾|思客智库|全球连线|教育|科技|科创|量子|体育|文化|书画|健康|军事|访谈|视频|图片|政务|法律|中央文件|金融|汽车|食品|人居|信息化|数字经济|学术中国|乡村振兴|银龄|溯源中国|城市|旅游|能源|会展|彩票|娱乐|时尚|悦读|公益|一带一路|亚太网|上市公司|文化产业)\s*$',
        # Markdown 列表格式: * 北京、天津、河北 等地方
        r'^\*\s*(?:北京|天津|河北|山西|辽宁|吉林|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|内蒙古|黑龙江)\s*$',
        # Markdown 列表格式: * English、Español 等多语种
        r'^\*\s*(?:English|Español|Français|عربى|Русский\s*язык|日本語|한국어|Deutsch|Português)\s*$',
        # 纯文字栏目名（不带星号）
        r'^(?:学习进行时|高层|时政|人事|国际|财经|网评|港澳|台湾|思客智库|全球连线|教育|科技|科创|量子|体育|文化|书画|健康|军事|访谈|视频|图片|政务|法律|中央文件)\s*$',
        r'^(?:北京|天津|河北|山西|辽宁|吉林|上海|江苏|浙江|安徽|福建|江西|山东|河南|湖北|湖南|广东|广西|海南|重庆|四川|贵州|云南|西藏|陕西|甘肃|青海|宁夏|新疆|内蒙古|黑龙江)\s*$',
    ]
    for pattern in category_list_patterns:
        content = re.sub(pattern, '', content, flags=re.MULTILINE | re.IGNORECASE)

    # 23. 去除 SVG/XML 等代码残留（Play Video、Path 等）
    content = re.sub(r"Play\s*Video\s*", '', content)
    content = re.sub(r"id='[^']*'\s*fill='[^']*'\s*stroke='[^']*'\s*/[^>]*>", '', content)
    content = re.sub(r"<[^>]+>", '', content)  # 去除剩余的 HTML/XML 标签

    # 24. 再次清理空行
    lines = [line.strip() for line in content.split('\n')]
    content = '\n'.join(line for line in lines if line)

    return content.strip()


def extract_title_from_content(content: str) -> str:
    """
    从文章内容中提取标题

    优先顺序：
    1. Markdown 图片链接格式中的文字: ![标题](url)
    2. Markdown 链接格式中的文字: [标题](url)
    3. 第一个非空行如果看起来像标题（10-50字符，无标点结尾）
    4. 从来源/作者行之前的内容中提取
    """
    if not content:
        return ""
    
    # 常见的无意义标题，跳过
    skip_titles = {
        '回到顶部', '返回', '首页', '上一页', '下一页',
        '更多', '查看全文', '点击查看', '展开', '收起',
        'javascript:void(0)', 'javascript:;', '#', '',
    }

    lines = [l.strip() for l in content.split('\n') if l.strip()]

    # 1. 尝试从 Markdown 图片链接提取标题: ![标题](url)
    for line in lines:
        img_match = re.match(r'^!\[([^\]]*)\]\([^)]+\)$', line)
        if img_match:
            title = img_match.group(1).strip()
            if title and title not in skip_titles and len(title) >= 4:
                # 进一步检查：不能是纯数字或纯符号
                if not title.isdigit() and not re.match(r'^[\W_]+$', title):
                    return title

    # 2. 尝试从 Markdown 链接提取标题: [标题](url)
    for line in lines:
        link_match = re.match(r'^\[([^\]]+)\]\([^)]+\)$', line)
        if link_match:
            title = link_match.group(1).strip()
            if (title and title not in skip_titles and len(title) >= 4 
                and not title.startswith('!') and not title.isdigit()
                and not re.match(r'^[\W_]+$', title)):
                return title

    # 3. 查找 "来源：" 或 "作者：" 行之前的标题行
    for i, line in enumerate(lines):
        if '来源：' in line or '作者：' in line:
            # 向前查找第一个可能是标题的行
            for j in range(i-1, -1, -1):
                prev = lines[j]
                # 跳过链接行和空行
                if prev.startswith('[') or prev.startswith('![') or prev.startswith('#'):
                    continue
                # 跳过纯分隔符行: === 或 --- 或 *** 等
                if prev and re.match(r'^[\-\=\*]{3,}$', prev):
                    continue
                if prev in skip_titles or len(prev) < 4:
                    continue
                if 10 <= len(prev) <= 60:
                    not_title_endings = ('。', '！', '？', '.', '!', '?', '，', '；', ',', '-')
                    if not prev.endswith(not_title_endings):
                        return prev

    # 4. 第一行如果看起来像标题
    for line in lines[:5]:
        if line.startswith('![') or line.startswith('[') or line.startswith('-') or line.startswith('#'):
            continue
        if line in skip_titles or len(line) < 4:
            continue
        not_title_endings = ('。', '！', '？', '.', '!', '?', '，', '；', ',', '-')
        if 10 <= len(line) <= 50 and not line.endswith(not_title_endings):
            chinese_ratio = sum(1 for c in line if '\u4e00' <= c <= '\u9fff') / len(line)
            if chinese_ratio >= 0.5:
                return line

    return ""


def format_content_with_summary(content: str, summary: str) -> str:
    """
    将摘要和原文组合成最终内容

    格式：
    【摘要】
    摘要内容

    【正文】
    原文内容
    """
    if summary:
        return f"""【摘要】
{summary}

【正文】
{content}"""
    return content


# ================================================
# 进度事件管理器（用于SSE实时推送）
# ================================================
class ScrapeProgress:
    """爬取进度事件管理器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._callbacks = []
            cls._instance._current_progress = {}
        return cls._instance

    def subscribe(self, callback):
        self._callbacks.append(callback)
        return lambda: self._callbacks.remove(callback)

    def emit(self, scrape_id: str, event: str, data: dict):
        event_data = {
            "scrape_id": scrape_id,
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        self._current_progress[scrape_id] = event_data
        for callback in self._callbacks:
            try:
                callback(event_data)
            except Exception:
                pass

    def set_progress(self, scrape_id: str, progress: dict):
        self._current_progress[scrape_id] = {
            **progress,
            "scrape_id": scrape_id,
            "timestamp": datetime.now().isoformat(),
        }

    def get_progress(self, scrape_id: str) -> dict:
        return self._current_progress.get(scrape_id, {})

    def clear_progress(self, scrape_id: str):
        self._current_progress.pop(scrape_id, None)


progress_manager = ScrapeProgress()


# ================================================
# 爬取专用日志记录器
# ================================================
class ScrapeLogger:
    """爬取日志记录器"""

    def __init__(self, log_dir: str = "logs", log_file: str = "scrape.log"):
        from pathlib import Path
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / log_file
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger("scrape_logger")
        self.logger.setLevel(logging.DEBUG)
        if not self.logger.handlers:
            handler = logging.FileHandler(self.log_file, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
            self.logger.addHandler(handler)

    def info(self, msg: str):
        self.logger.info(msg)

    def log_scrape_result(self, url: str, status: str, word_count: int, title: str = ""):
        title_preview = title[:40] + "..." if len(title) > 40 else title
        self.info(f"爬取结果 | 状态: {status} | 字数: {word_count} | 标题: {title_preview}")

    def log_article_links(self, url: str, links: List[str]):
        self.info(f"文章链接识别 | 来源: {url} | 数量: {len(links)}")
        for i, link in enumerate(links[:10], 1):
            self.info(f"  {i}. {link}")


scrape_logger = ScrapeLogger()

# ================================================
# 日期验证常量
# ================================================
MIN_VALID_YEAR = 2000
MAX_FUTURE_DAYS = 1  # 允许未来1天（时区误差）
MAX_AGE_YEARS = 10   # 文章最长10年

# ================================================
# 内容质量阈值
# ================================================
MIN_CONTENT_WORDS = 50  # 内容最少字数


@dataclass
class ScrapeOptions:
    """爬取选项"""
    extract_content: bool = True
    fetch_html: bool = False
    preserve_format: bool = False
    max_depth: int = 0
    timeout: int = 30
    extract_metadata: bool = True


@dataclass
class ScrapedResult:
    """爬取结果"""
    url: str
    title: str = ""
    content: str = ""
    html: str = ""
    word_count: int = 0
    links: List[str] = field(default_factory=list)
    status: str = "pending"
    error_message: Optional[str] = None
    scraped_at: Optional[str] = None
    published_at: Optional[str] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

    def __post_init__(self):
        if self.links is None:
            self.links = []
        if self.keywords is None:
            self.keywords = []
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()


class DateExtractor:
    """
    日期提取器（核心组件）
    严格按优先级提取和验证日期
    """

    # URL 日期正则模式（按优先级）
    # 每个元组: (正则模式, 处理函数)
    # 处理函数接收匹配的组，返回格式化的日期字符串
    URL_DATE_PATTERNS = [
        # 1. /YYYYMMDD/ 目录格式（如 /20260630/）- 最精确
        (r'/(\d{4})(\d{2})(\d{2})/', lambda g: f"{g[0]}-{g[1]}-{g[2]}"),
        # 2. /YYYY/MM/DD/ 格式（如 /2026/06/30/）
        (r'/(\d{4})/(\d{2})/(\d{2})/', lambda g: f"{g[0]}-{g[1]}-{g[2]}"),
        # 3. /YYYYMM/tYYYYMMDD 格式（如 /202606/t20260630_xxx.shtml）
        (r'/t(\d{4})(\d{2})(\d{2})[_\.]', lambda g: f"{g[0]}-{g[1]}-{g[2]}"),
        # 4. 文件名开始8位日期 + 字母 /20260630abc.html
        (r'/(\d{8})[a-zA-Z0-9]+\.[a-z]+', lambda g: f"{g[0][:4]}-{g[0][4:6]}-{g[0][6:8]}"),
        # 5. 文件名8位日期 /20260630.html 等
        (r'/(\d{8})\.[a-z]+', lambda g: f"{g[0][:4]}-{g[0][4:6]}-{g[0][6:8]}"),
    ]

    # URL 参数日期格式
    URL_PARAM_PATTERNS = [
        r'[?&](?:date|time|publish|created?|updated?)=(\d{8})',
        r'[?&](?:date|time|publish|created?|updated?)=(\d{4}-\d{2}-\d{2})',
    ]

    @classmethod
    def extract_from_url(cls, url: str) -> Optional[str]:
        """
        从 URL 提取日期（最可靠）

        支持的格式：
        - /20260630/ - 直接8位日期
        - /2026/06/30/ - 斜杠分隔
        - /202606/t20260630_xxx.html - t+8位日期
        - /xxx/20260630.html - 文件名8位日期
        - ?date=20260630 - URL参数
        """
        # 1. 优先匹配目录日期模式
        for pattern, fmt in cls.URL_DATE_PATTERNS:
            match = re.search(pattern, url)
            if match:
                try:
                    groups = match.groups()
                    if callable(fmt):
                        date_str = fmt(groups)
                    else:
                        date_str = fmt % groups
                    if cls._validate_date(date_str):
                        return date_str
                except:
                    continue

        # 2. URL 参数日期
        for pattern in cls.URL_PARAM_PATTERNS:
            match = re.search(pattern, url)
            if match:
                date_str = match.group(1)
                if len(date_str) == 8:  # YYYYMMDD
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                if cls._validate_date(date_str):
                    return date_str

        return None

    @classmethod
    def _validate_date(cls, date_str: str) -> bool:
        """
        严格验证日期是否合理
        """
        try:
            parsed = datetime.strptime(date_str, "%Y-%m-%d")
            d = parsed.date()
            today = date.today()

            # 1. 不能是未来日期（允许1天误差）
            if d > today + timedelta(days=MAX_FUTURE_DAYS):
                return False

            # 2. 不能太早（早于2000年）
            if d.year < MIN_VALID_YEAR:
                return False

            # 3. 不能太老（超过10年）
            age = (today - d).days / 365
            if age > MAX_AGE_YEARS:
                return False

            return True
        except (ValueError, TypeError):
            return False

    @classmethod
    def extract_from_html(cls, html: str) -> Optional[str]:
        """
        从 HTML 提取日期（次优选择）
        """
        # 1. <time> 元素
        time_match = re.search(r'<time[^>]+datetime=["\']?(\d{4}-\d{2}-\d{2})', html)
        if time_match and cls._validate_date(time_match.group(1)):
            return time_match.group(1)

        # 2. JSON-LD
        json_match = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        if json_match:
            date_str = json_match.group(1).split('T')[0]
            if cls._validate_date(date_str):
                return date_str

        # 3. 专用发布日期属性（中文网站常用）
        date_patterns = [
            r'<[^>]+class=["\'][^"\']*time[^"\']*["\'][^>]*>(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
            r'<[^>]+class=["\'][^"\']*date[^"\']*["\'][^>]*>(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
            r'<[^>]+class=["\'][^"\']*pub[^"\']*["\'][^>]*>(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, html)
            if match:
                date_str = cls._normalize_chinese_date(match.group(1))
                if date_str and cls._validate_date(date_str):
                    return date_str

        # 4. Meta 标签（谨慎使用，部分网站的 Meta 日期不准确）
        meta_patterns = [
            r'<meta[^>]+property=["\']article:published_time["\'][^>]+content=["\']([^"\']+)',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']article:published_time["\']',
        ]
        for pattern in meta_patterns:
            match = re.search(pattern, html)
            if match:
                date_str = match.group(1).split('T')[0]
                if cls._validate_date(date_str):
                    return date_str

        return None

    @classmethod
    def _normalize_chinese_date(cls, date_str: str) -> Optional[str]:
        """规范化中文日期格式为 YYYY-MM-DD"""
        try:
            # 年月日格式
            date_str = date_str.replace('年', '-').replace('月', '-').replace('日', '')
            # 统一分隔符
            date_str = date_str.replace('/', '-')
            # 解析
            parts = date_str.split('-')
            if len(parts) >= 3:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                return f"{year:04d}-{month:02d}-{day:02d}"
        except:
            pass
        return None


class FirecrawlClient:
    """
    Firecrawl API 客户端
    支持本地和远程两种模式
    """

    # 远程 API 默认地址
    REMOTE_BASE_URL = "https://api.firecrawl.dev/v0"
    LOCAL_BASE_URL = "http://localhost:3002"

    def __init__(self, api_key: Optional[str] = None, use_local: bool = False, local_url: Optional[str] = None):
        """
        初始化 Firecrawl 客户端

        Args:
            api_key: API Key（远程模式必需，本地模式可填 "local"）
            use_local: 是否使用本地服务
            local_url: 本地服务地址
        """
        self.use_local = use_local
        self.local_url = local_url or self.LOCAL_BASE_URL
        self.api_key = api_key or self._get_api_key()

        if self.use_local:
            self.base_url = self.local_url
        else:
            self.base_url = self.REMOTE_BASE_URL

    def _get_api_key(self) -> str:
        """获取 API Key（从环境变量）"""
        import os
        return os.environ.get("FIRECRAWL_API_KEY", "")

    def _load_config_from_settings(self) -> None:
        """从设置中加载配置"""
        try:
            from app.api.settings import settings_store
            config = settings_store.get_firecrawl_config()
            self.use_local = config.use_local
            self.local_url = config.local_url
            self.api_key = config.api_key or self.api_key
            self.base_url = self.local_url if self.use_local else self.REMOTE_BASE_URL
        except Exception:
            pass

    async def scrape_url(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        """
        爬取单个 URL

        Returns:
            Dict with keys: success, content, markdown, title, links, metadata
        """
        # 如果未指定模式，尝试从设置加载
        if self.api_key is None and self.local_url == self.LOCAL_BASE_URL:
            self._load_config_from_settings()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 根据本地/远程模式构造请求体
        if self.use_local:
            # 本地服务使用 v1 API
            payload = {
                "url": url,
                "formats": ["markdown", "html", "links"],
            }
            endpoint = "/v1/scrape"
        else:
            # 远程服务使用 v0 API
            payload = {
                "url": url,
                "pageOptions": {
                    "onlyMainContent": False,
                },
                "extractOptions": {
                    "mode": "markdown",
                }
            }
            endpoint = "/scrape"

        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}{endpoint}",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                if self.use_local:
                    # 本地服务返回格式
                    if data.get("success"):
                        return {
                            "success": True,
                            "content": data.get("data", {}).get("markdown", ""),
                            "markdown": data.get("data", {}).get("markdown", ""),
                            "title": data.get("data", {}).get("metadata", {}).get("title", ""),
                            "links": data.get("data", {}).get("links", []),
                            "html": data.get("data", {}).get("html", ""),
                            "metadata": data.get("data", {}).get("metadata", {}),
                        }
                    else:
                        return {"success": False, "error": data.get("error", "Unknown error")}
                else:
                    # 远程服务返回格式
                    if data.get("success"):
                        return {
                            "success": True,
                            "content": data.get("data", {}).get("content", ""),
                            "markdown": data.get("data", {}).get("markdown", ""),
                            "title": data.get("data", {}).get("metadata", {}).get("title", ""),
                            "links": data.get("data", {}).get("links", []),
                            "html": data.get("data", {}).get("html", ""),
                            "metadata": data.get("data", {}).get("metadata", {}),
                        }
                    else:
                        return {"success": False, "error": data.get("error", "Unknown error")}
            except httpx.TimeoutException:
                return {"success": False, "error": "Request timeout"}
            except Exception as e:
                return {"success": False, "error": str(e)}

    async def scrape_batch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """批量爬取"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.use_local:
            # 本地服务：循环调用单个抓取
            results = []
            for url in urls:
                result = await self.scrape_url(url)
                results.append(result)
            return results
        else:
            # 远程服务：使用批量接口
            payload = {"urls": urls}
            async with httpx.AsyncClient(timeout=120) as client:
                try:
                    response = await client.post(
                        f"{self.base_url}/batch-scrape",
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.json().get("data", [])
                except Exception as e:
                    logger.error(f"批量爬取失败: {e}")
                    return []


# 全局 Firecrawl 客户端
_firecrawl_client: Optional[FirecrawlClient] = None


def get_firecrawl_client(use_local: Optional[bool] = None) -> FirecrawlClient:
    """
    获取全局 Firecrawl 客户端

    Args:
        use_local: 强制指定使用本地/远程模式，None 则从设置读取
    """
    global _firecrawl_client

    # 如果有强制指定模式，重建客户端
    if use_local is not None and _firecrawl_client is not None:
        if _firecrawl_client.use_local != use_local:
            _firecrawl_client = None

    if _firecrawl_client is None:
        # 从设置中读取配置
        try:
            from app.api.settings import settings_store
            config = settings_store.get_firecrawl_config()
            _firecrawl_client = FirecrawlClient(
                api_key=config.api_key,
                use_local=config.use_local,
                local_url=config.local_url
            )
        except Exception:
            # 如果无法获取设置，使用默认值
            _firecrawl_client = FirecrawlClient()

    # 如果有强制指定模式但客户端已存在，更新它
    if use_local is not None:
        _firecrawl_client.use_local = use_local
        _firecrawl_client.base_url = _firecrawl_client.local_url if use_local else FirecrawlClient.REMOTE_BASE_URL

    return _firecrawl_client


def reset_firecrawl_client() -> None:
    """重置 Firecrawl 客户端（下次调用时会重新初始化）"""
    global _firecrawl_client
    _firecrawl_client = None


class WebScraper:
    """
    网页爬取引擎
    使用 Firecrawl + URL 日期提取 + LLM 摘要
    """

    def __init__(self, cancel_event: Optional[asyncio.Event] = None, progress_callback: Optional[callable] = None):
        self._llm_service = None
        self._cancel_event = cancel_event
        self._firecrawl = get_firecrawl_client()
        self._progress_callback = progress_callback

    def _is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancel_event is not None and self._cancel_event.is_set()

    def _get_llm_service(self):
        """获取 LLM 服务"""
        if self._llm_service is None:
            from app.core.llm import llm_service
            self._llm_service = llm_service
        return self._llm_service

    def _extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """从 HTML 提取链接"""
        links = []
        pattern = r'<a[^>]+href=["\']([^"\']+)["\']'
        for match in re.finditer(pattern, html):
            href = match.group(1)
            if href and not href.startswith(('#', 'javascript:', 'mailto:', 'tel:')):
                if href.startswith('http'):
                    links.append(href)
                else:
                    links.append(urljoin(base_url, href))
        return list(set(links))

    async def scrape(self, url: str, options: Optional[ScrapeOptions] = None) -> ScrapedResult:
        """
        爬取单个网页

        1. Firecrawl 爬取内容
        2. URL 日期提取（最优先）
        3. LLM 摘要提取（可选）
        """
        if options is None:
            options = ScrapeOptions()

        result = ScrapedResult(url=url)
        logger.info(f"开始爬取: {url}")

        try:
            # 1. Firecrawl 爬取
            scrape_result = await self._firecrawl.scrape_url(url, timeout=options.timeout)

            if not scrape_result.get("success"):
                result.status = "error"
                result.error_message = scrape_result.get("error", "爬取失败")
                logger.error(f"爬取失败: {url}, 错误: {result.error_message}")
                return result

            # 2. 提取内容
            raw_html = scrape_result.get("html", "")
            markdown = scrape_result.get("markdown", "")
            raw_content = markdown.strip() if markdown else scrape_result.get("content", "")

            # 清理内容
            result.content = clean_content(raw_content)
            result.html = raw_html

            # 尝试获取标题：先从 metadata 获取，如果没有则从内容提取
            result.title = scrape_result.get("title", "")
            if not result.title:
                result.title = extract_title_from_content(result.content)

            result.links = self._extract_links_from_html(raw_html, url)
            result.word_count = len(result.content.replace("\n", "").replace(" ", ""))

            # 3. 检测是否为列表页（通过内容判断）
            if self._is_list_page(result.content, result.links):
                logger.info(f"检测为列表页，跳过正文提取: {url}")
                result.content = ""
                result.word_count = 0
                result.status = "success"
                return result

            # 4. 日期提取（内容日期优先，URL 日期作为参考）
            url_date = DateExtractor.extract_from_url(url)
            content_date, content_author = extract_date_from_content(result.content, url)

            # 内容日期具有更高权威性，优先使用
            if content_date:
                result.published_at = content_date
                logger.debug(f"内容日期: {content_date}")

                # 如果有 URL 日期，记录日志以对比
                if url_date:
                    logger.debug(f"URL 日期: {url_date} -> 被内容日期覆盖")
            elif url_date:
                # 没有内容日期时，使用 URL 日期
                result.published_at = url_date
                logger.debug(f"URL 日期: {url_date}")

            # 同时提取作者
            if content_author and not result.author:
                result.author = content_author
                logger.debug(f"内容作者: {content_author}")

            # 5. 大模型提取元信息（如需要）
            if options.extract_metadata and result.content and result.word_count >= 50:
                metadata = await self._extract_metadata_with_llm(result.title, result.content, result.url)
                logger.info(f"LLM 元信息提取结果: title={len(metadata.get('title', ''))}字, summary={len(metadata.get('summary', ''))}字, keywords={len(metadata.get('keywords', []))}个")

                # 优先使用 LLM 提取的标题
                if metadata.get("title") and len(metadata.get("title", "")) > len(result.title):
                    result.title = metadata["title"]

                # 只在未从内容提取到作者时才使用 LLM 提取的
                if not result.author and metadata.get("author"):
                    result.author = metadata.get("author")

                result.summary = metadata.get("summary", "") or metadata.get("摘要", "")
                logger.info(f"设置的摘要: {result.summary[:50] if result.summary else '空'}...")

                result.keywords = metadata.get("keywords", [])

                # 如果没有 URL 日期也没有内容日期，用 LLM 日期（兜底）
                if not result.published_at and metadata.get("published_at"):
                    if DateExtractor._validate_date(metadata["published_at"]):
                        result.published_at = metadata["published_at"]

                # 将摘要组合到内容前面
                if result.summary:
                    result.content = format_content_with_summary(result.content, result.summary)
                    logger.info("摘要已添加到内容前面")

            result.status = "success"
            logger.info(f"爬取成功: {url}, 字数: {result.word_count}, 日期: {result.published_at}")

        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            logger.error(f"爬取异常: {url}, 错误: {e}")

        return result

    def _is_list_page(self, content: str, links: List[str]) -> bool:
        """判断是否为列表页（只有内容真正很少时才认为是列表页）"""
        # 只有内容非常少时才认为是列表页
        if len(content) < 100:
            return True

        # 如果有链接且内容有实质内容，认为是文章页
        # 文章通常有足够的句子结构（英文用句号判断）
        if len(content) > 300 and links:
            # 检查是否有句子结构
            sentence_markers = content.count('.') + content.count('。') + content.count('!') + content.count('?')
            if sentence_markers >= 3:
                return False

        return False

    async def _extract_metadata_with_llm(self, title: str, content: str, url: str = "") -> Dict[str, Any]:
        """使用大模型提取元信息，包括标题和摘要"""
        try:
            llm = self._get_llm_service()

            # 准备提示词 - 始终包含标题和内容以提取摘要
            content_preview = content[:5000]  # 限制内容长度

            prompt = f"""你是一位专业的内容分析师。请分析以下文章，提取关键信息。

文章标题：{title if title else "（未找到标题）"}

文章内容：
{content_preview}

请仔细阅读文章内容，提取以下信息：

1. **标题**：如果原文没有明确标题，请根据文章主题提取一个简洁的标题（不超过40个字符）
2. **作者/来源**：文章的作者或发布来源（如有）
3. **发布日期**：如果文中提到，格式为 YYYY-MM-DD；如未提及则返回空字符串
4. **摘要**：用100-150字概括文章的核心内容，包括主题、核心观点和结论（非常重要！）
5. **关键词**：提取3-5个最重要的关键词（用逗号分隔）

请以JSON格式返回结果，确保JSON格式完全正确：
{{"title":"","author":"","published_at":"","summary":"","keywords":[]}}

只返回JSON，不要添加任何解释或其他内容。"""

            response = await llm.non_stream_chat(
                model_id="",
                messages=[{"role": "user", "content": prompt}],
            )

            logger.info(f"LLM 原始响应: {response[:500]}...")

            if response and not response.startswith("[错误]"):
                # 提取 JSON
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        data = json.loads(json_match.group())
                        # 确保 keywords 是列表（处理各种可能的格式）
                        keywords_raw = data.get("keywords", [])
                        keywords = []
                        if isinstance(keywords_raw, str):
                            # 如果是逗号分隔的字符串，转换为列表
                            keywords = [k.strip() for k in keywords_raw.split(',') if k.strip()]
                        elif isinstance(keywords_raw, list):
                            for k in keywords_raw:
                                if isinstance(k, str):
                                    # 如果元素本身包含逗号，再分割
                                    parts = [x.strip() for x in k.split(',') if x.strip()]
                                    keywords.extend(parts)
                                elif k:
                                    keywords.append(str(k).strip())
                        keywords = [k for k in keywords if k]  # 去重后去除空值
                        
                        return {
                            "title": data.get("title", title) if title or not data.get("title") else data.get("title"),
                            "published_at": data.get("published_at", ""),
                            "author": data.get("author", ""),
                            "summary": data.get("summary", "") or data.get("摘要", ""),
                            "keywords": keywords,
                        }
                    except json.JSONDecodeError as je:
                        logger.error(f"JSON解析失败: {je}, 原始响应: {response[:500]}")
        except Exception as e:
            logger.error(f"LLM 元信息提取失败: {e}")

        return {"title": title, "published_at": "", "author": "", "summary": "", "keywords": []}

    async def scrape_batch(
        self,
        urls: List[str],
        options: Optional[ScrapeOptions] = None,
        max_concurrent: int = 3
    ) -> List[ScrapedResult]:
        """批量爬取"""
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_limit(url: str) -> ScrapedResult:
            async with semaphore:
                return await self.scrape(url, options)

        tasks = [scrape_with_limit(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [
            r if not isinstance(r, Exception) else ScrapedResult(url=urls[i], status="error", error_message=str(r))
            for i, r in enumerate(results)
        ]

    async def deep_scrape(
        self,
        url: str,
        options: Optional[ScrapeOptions] = None,
        max_articles: int = 10,
        date_range: Optional[str] = None,
        custom_date_range: Optional[dict] = None,
        scrape_level: Optional[str] = "deep",
        scrape_id: Optional[str] = None,
        progress_callback: Optional[callable] = None
    ) -> tuple[ScrapedResult, List[ScrapedResult]]:
        """
        深度爬取：从列表页识别文章链接，爬取文章内容
        """
        import uuid
        if scrape_id is None:
            scrape_id = str(uuid.uuid4())[:8]

        logger.info(f"深度爬取开始 | URL: {url} | 日期范围: {date_range or custom_date_range}")

        if options is None:
            options = ScrapeOptions()

        # 1. 爬取列表页
        logger.info(f"解析列表页: {url}")
        list_page = await self.scrape(url, options)
        list_page.title = list_page.title or "列表页"

        if list_page.status != "success":
            return list_page, []

        # 2. 识别文章链接（基于 URL 模式）
        article_links = self._filter_article_links(list_page.links, url)
        # 使用回调更新进度
        cb = progress_callback or self._progress_callback
        if cb:
            cb(2, "正在爬取文章", f"识别到 {len(article_links)} 个链接，开始爬取...")
        
        logger.info(f"识别到 {len(article_links)} 个文章链接")

        if not article_links:
            return list_page, []

        # 限制数量
        article_links = article_links[:max_articles * 2]

        # 3. 如果有日期范围，先根据URL日期预过滤（避免爬取不需要的文章）
        if date_range or custom_date_range:
            today = date.today()
            if date_range == "today":
                start_date, end_date = today, today
            elif date_range == "week":
                start_date, end_date = today - timedelta(days=7), today
            elif date_range == "month":
                start_date, end_date = today - timedelta(days=30), today
            elif custom_date_range:
                start_date = custom_date_range.get("start_date") or date(2000, 1, 1)
                end_date = custom_date_range.get("end_date") or today
            else:
                start_date, end_date = None, None

            if start_date and end_date:
                logger.info(f"URL日期预过滤: [{start_date} ~ {end_date}]")
                # 从URL提取日期进行预过滤
                filtered_links = []
                no_date_count = 0
                for link in article_links:
                    url_date = DateExtractor.extract_from_url(link)
                    if url_date:
                        try:
                            d = datetime.strptime(url_date, "%Y-%m-%d").date()
                            if start_date <= d <= end_date:
                                filtered_links.append(link)
                            else:
                                logger.debug(f"预过滤(日期不符): {link}")
                        except Exception as e:
                            logger.debug(f"预过滤(日期解析失败): {link}")
                            no_date_count += 1
                    else:
                        no_date_count += 1
                        logger.debug(f"预过滤(无日期): {link}")

                logger.info(f"URL日期预过滤: {len(article_links)} -> {len(filtered_links)} 篇 (无日期: {no_date_count})")
                article_links = filtered_links

                # 更新进度
                if cb:
                    cb(2, "正在爬取文章", f"识别到 {len(article_links)} 个符合日期的文章", total=len(article_links))

        # 3. 批量爬取文章（逐个爬取并更新进度）
        if not article_links:
            logger.info("没有符合日期条件的文章链接")
            return list_page, []

        logger.info(f"开始爬取 {len(article_links)} 篇文章")
        article_results = []
        for i, article_url in enumerate(article_links):
            if self._is_cancelled():
                logger.info("爬取已取消")
                break
            result = await self.scrape(article_url, options)
            article_results.append(result)
            # 每爬取一篇更新一次进度
            if cb:
                cb(3, f"正在爬取 ({i+1}/{len(article_links)})", f"已爬取 {len(article_results)} 篇", current=i+1, total=len(article_links))

        # 4. 处理结果
        valid_results = [r for r in article_results if r.status == "success" and r.word_count > 0]
        logger.info(f"有效文章: {len(valid_results)} 篇")

        # 5. 为每篇文章补充 URL 日期（如没有）
        for r in valid_results:
            if not r.published_at:
                url_date = DateExtractor.extract_from_url(r.url)
                if url_date:
                    r.published_at = url_date

        # 6. 日期过滤
        logger.info(f"日期过滤检查 | date_range={date_range} | custom={custom_date_range}")
        if date_range or custom_date_range:
            today = date.today()
            if date_range == "today":
                start_date, end_date = today, today
            elif date_range == "week":
                start_date, end_date = today - timedelta(days=7), today
            elif date_range == "month":
                start_date, end_date = today - timedelta(days=30), today
            elif custom_date_range:
                start_date = custom_date_range.get("start_date") or date(2000, 1, 1)
                end_date = custom_date_range.get("end_date") or today
            else:
                start_date, end_date = None, None

            logger.info(f"日期范围: [{start_date} ~ {end_date}]")

            if start_date and end_date:
                # 确保起始日期 <= 结束日期
                if start_date > end_date:
                    start_date, end_date = end_date, start_date

                before_count = len(valid_results)
                # 详细日志：显示每篇文章的日期
                for r in valid_results:
                    logger.info(f"  文章日期检查: {r.title[:30]}... -> {r.published_at}")

                valid_results = [
                    r for r in valid_results
                    if r.published_at and self._date_in_range(r.published_at, start_date, end_date)
                ]
                logger.info(f"日期过滤 [{start_date} ~ {end_date}]: {before_count} -> {len(valid_results)} 篇")

        # 7. 按日期排序（最新的在前）
        valid_results = self._sort_by_date(valid_results)

        # 8. 限制最终数量
        valid_results = valid_results[:max_articles]

        logger.info(f"深度爬取完成: {len(valid_results)} 篇文章")
        return list_page, valid_results

    def _filter_article_links(self, links: List[str], base_url: str) -> List[str]:
        """过滤出文章链接，只保留与列表页同栏目的文章"""
        parsed_base = urlparse(base_url)
        domain = parsed_base.netloc
        base_path = parsed_base.path

        # 从列表页 URL 提取主栏目名称
        # 例如: https://www.cas.cn/yw/ -> main_category = "yw"
        #       https://aircas.ac.cn/dqyd/gzdt/ -> main_category = "dqyd"
        path_parts = base_path.strip('/').split('/')
        main_category = path_parts[0] if path_parts else ""

        logger.info(f"主栏目: /{main_category}/ (来自: {base_url})")

        article_links = []

        # 跳过模式（导航、地图、登录等无意义链接）
        skip_patterns = [
            # 通用导航模式
            'login', 'register', 'about', 'contact', 'search',
            'index.html', 'index.htm', 'page=', '/page/',
            # 网站地图和导航
            'sitemap', 'site-map', '网站地图', 'map', 'nav', '导航',
            'menu', 'menus', 'sidebar', 'footer', 'header',
            # 语言切换
            'english', '/en/', '/eng/', 'locale', 'language', 'lang=',
            '邮箱登录', 'login.html', 'login.htm',
            # 联系我们和版权
            '联系我们', 'copyright', '版權', '版权所有',
            # 面包屑当前位置（首页、当前位置等）
            '首页', 'home', 'current', '当前位置', '您现在的位置',
            # 常见站点导航
            '党群园地', '工作动态', '组织机构', '科普园地',
            # 其他无用链接
            'share', 'share.html', '收藏', 'favorite', 'bookmark',
        ]

        # 文章链接特征（更严格的要求）
        for link in links:
            if not link or link.startswith(('javascript:', '#', 'mailto:')):
                continue

            # 同域名检查
            parsed = urlparse(link)
            if parsed.netloc and parsed.netloc != domain:
                continue

            # 转换为小写用于模式匹配
            link_lower = link.lower()

            # 跳过模式
            if any(p in link_lower for p in skip_patterns):
                continue

            # 文章链接特征检查
            # 日期模式：/YYYYMM/ 或 /YYYYMMDD/ 或 tYYYYMMDD
            has_date_in_url = bool(re.search(r'/(\d{6}|\d{8})/', link)) or bool(re.search(r'/t\d{8}', link))
            # 文件扩展名
            has_file_ext = any(link.endswith(ext) for ext in ['.html', '.htm', '.shtml', '.php'])

            # 栏目检查：只接受主栏目路径下的文章
            # 例如：列表页 /yw/ -> 只接受 /yw/202606/xxx.shtml
            #       不接受 /djcx/gz/202606/xxx.shtml
            link_path = urlparse(link).path
            link_parts = link_path.strip('/').split('/')
            # 文章 URL 格式通常是: /主栏目/日期/xxx.shtml
            # 所以第一个路径段应该是主栏目名
            is_same_category = len(link_parts) > 1 and link_parts[0] == main_category

            # 如果列表页是根路径（如 /），允许所有链接
            if not main_category:
                is_same_category = True

            if has_date_in_url and has_file_ext and is_same_category:
                article_links.append(link)
                logger.debug(f"  接受: {link}")
            elif has_date_in_url and has_file_ext and not is_same_category:
                logger.debug(f"  过滤(不同栏目): {link}")

        logger.info(f"文章链接过滤完成: 识别到 {len(article_links)} 个 /{main_category}/ 栏目链接")
        return list(set(article_links))

    def _date_in_range(self, date_str: str, start: date, end: date) -> bool:
        """检查日期是否在范围内"""
        try:
            # 允许交换 start/end
            if start > end:
                start, end = end, start

            parsed = datetime.strptime(date_str, "%Y-%m-%d").date()
            return start <= parsed <= end
        except (ValueError, TypeError):
            return False

    def _sort_by_date(self, results: List[ScrapedResult]) -> List[ScrapedResult]:
        """按日期排序（最新的在前）"""
        def get_sort_key(r: ScrapedResult) -> tuple:
            if not r.published_at:
                return (1, date.min)
            try:
                return (0, datetime.strptime(r.published_at, "%Y-%m-%d").date())
            except:
                return (1, date.min)

        return sorted(results, key=get_sort_key, reverse=True)


def get_scraper() -> WebScraper:
    """获取爬取器实例"""
    return WebScraper()