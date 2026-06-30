"""
网页爬取服务
使用 crawl4ai 支持静态和动态网页爬取
使用智能提取器提取页面正文
使用 LLM 提取文章元信息（摘要、作者、发布时间、关键词）
"""

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta

if TYPE_CHECKING:
    from bs4 import BeautifulSoup

from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from app.services.website_classifier import WebsiteClassifier, get_website_profile
from app.services.extractor_registry import ExtractorRegistry, smart_extract

logger = logging.getLogger(__name__)

# ================================================
# 内容质量最低阈值
# ================================================
MIN_CONTENT_WORDS = 50  # 内容少于50字的文章将被过滤（避免完全为空的内容）


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
        """订阅进度事件"""
        self._callbacks.append(callback)
        return lambda: self._callbacks.remove(callback)

    def emit(self, scrape_id: str, event: str, data: dict):
        """发送进度事件"""
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
        """设置进度状态（供轮询使用）"""
        self._current_progress[scrape_id] = {
            **progress,
            "scrape_id": scrape_id,
            "timestamp": datetime.now().isoformat(),
        }

    def get_progress(self, scrape_id: str) -> dict:
        """获取当前进度"""
        return self._current_progress.get(scrape_id, {})

    def clear_progress(self, scrape_id: str):
        """清除进度记录"""
        self._current_progress.pop(scrape_id, None)


progress_manager = ScrapeProgress()


# ================================================
# 爬取专用日志记录器
# ================================================
class ScrapeLogger:
    """爬取日志记录器 - 记录到文件"""

    def __init__(self, log_dir: str = "logs", log_file: str = "scrape.log"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / log_file
        self._setup_logger()

    def _setup_logger(self):
        """设置专用日志记录器"""
        self.logger = logging.getLogger("scrape_logger")
        self.logger.setLevel(logging.DEBUG)

        # 避免重复添加 handler
        if not self.logger.handlers:
            # 文件 Handler
            file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)
            self.logger.addHandler(file_handler)

            # 控制台 Handler
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            self.logger.addHandler(console_handler)

    def info(self, msg: str):
        self.logger.info(msg)

    def warning(self, msg: str):
        self.logger.warning(msg)

    def error(self, msg: str):
        self.logger.error(msg)

    def debug(self, msg: str):
        self.logger.debug(msg)

    def log_scrape_start(self, url: str, scrape_type: str = "single"):
        """记录爬取开始"""
        self.info(f"{'='*60}")
        self.info(f"爬取开始 | 类型: {scrape_type} | URL: {url}")

    def log_scrape_result(self, url: str, status: str, word_count: int, title: str = ""):
        """记录爬取结果"""
        title_preview = title[:40] + "..." if len(title) > 40 else title
        self.info(f"爬取结果 | 状态: {status} | 字数: {word_count} | 标题: {title_preview}")

    def log_article_links(self, url: str, links: List[str]):
        """记录识别的文章链接"""
        self.info(f"文章链接识别 | 来源: {url} | 数量: {len(links)}")
        for i, link in enumerate(links[:10], 1):
            self.info(f"  {i}. {link}")
        if len(links) > 10:
            self.info(f"  ... 还有 {len(links) - 10} 个链接")

    def log_deep_scrape_result(self, url: str, total: int, success: int, failed: int):
        """记录深度爬取结果"""
        self.info(f"深度爬取完成 | 列表页: {url}")
        self.info(f"  总文章数: {total} | 成功: {success} | 失败: {failed}")
        self.info("=" * 60)


# 单例实例
scrape_logger = ScrapeLogger()


@dataclass
class ScrapeOptions:
    """爬取选项"""
    extract_content: bool = True  # 提取正文
    fetch_html: bool = False  # 获取 HTML
    preserve_format: bool = False  # 保留格式
    max_depth: int = 0  # 爬取深度（0 = 不递归）
    timeout: int = 30  # 超时时间（秒）
    extract_metadata: bool = True  # 使用 LLM 提取元信息


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
    # 新增：文章元信息
    published_at: Optional[str] = None  # 发布时间
    author: Optional[str] = None  # 作者
    summary: Optional[str] = None  # 内容摘要
    keywords: List[str] = field(default_factory=list)  # 关键字标签

    def __post_init__(self):
        if self.links is None:
            self.links = []
        if self.keywords is None:
            self.keywords = []
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()


class WebScraper:
    """网页爬取引擎"""

    def __init__(self, cancel_event: Optional[asyncio.Event] = None):
        self._browser_config = BrowserConfig(
            headless=True,
            verbose=False,
        )
        self._llm_service = None  # 延迟初始化
        self._classifier = WebsiteClassifier()  # 网站类型识别器
        self._registry = ExtractorRegistry()  # 提取器注册表
        self._cancel_event = cancel_event  # 取消事件

    def _is_cancelled(self) -> bool:
        """检查是否已取消"""
        return self._cancel_event is not None and self._cancel_event.is_set()

    def _check_cancelled(self):
        """检查并抛出取消异常"""
        if self._is_cancelled():
            raise asyncio.CancelledError("爬取已取消")

    def _get_llm_service(self):
        """获取 LLM 服务（延迟加载避免循环导入）"""
        if self._llm_service is None:
            from app.core.llm import llm_service
            self._llm_service = llm_service
        return self._llm_service

    def _create_crawl_config(self, options: ScrapeOptions) -> CrawlerRunConfig:
        """创建爬取配置"""
        return CrawlerRunConfig(
            word_count_threshold=50,  # 最小字数阈值
            remove_overlay_elements=True,  # 移除弹窗
            page_timeout=options.timeout * 1000,  # 转换为毫秒
            process_iframes=True,  # 处理 iframe
            screenshot=False,  # 不截图
            exclude_external_images=True,  # 跳过外部图片
        )

    def _clean_html_content(self, content: str) -> str:
        """
        清理HTML内容，智能识别并过滤导航菜单、页脚等非正文内容

        Returns:
            str: 清理后的正文章节
        """
        import re

        # ========== 预定义关键字列表 ==========
        nav_keywords = [
            '首页', '组织机构', '主要职责', '办院方针', '院况简介', '院领导集体', '机构设置',
            '科学研究', '科技专项', '科技奖励', '科技期刊', '科研进展',
            '成果转化', '知识产权与科技成果转化网', '工作动态',
            '人才教育', '中国科学院教育简介', '中国科学技术大学', '中国科学院大学', '上海科技大学',
            '学部与院士', '院士之窗', '咨询委员会', '学部工作局',
            '科学普及', '科学与中国', '中国科普博览', '科普场馆',
            '党建与科学文化', '反腐倡廉', '文明天地', '统战工作',
            '信息公开', '信息公开规定', '信息公开指南', '信息公开目录', '信息公开申请', '信息公开联系方式',
            '联系我们', '网站地图', '邮箱', '无障碍', '关怀版',
            '网站标识码', '京ICP备', '京公网安备', '版权所有', '中国科学院版权所有',
            '地址：', '邮编：', '总机', '总值班室', '传真',
            '请按F11', '请注意', '该链接属站外链接', '无障碍辅助工具',
            '导航区', '视窗区', '交互区', '服务区', '列表区', '正文区',
            'ALT+', '快捷键', '读屏专用', '语音播报', '帮助',
            '打印', '浏览量', '扫一扫', '更多分享', '分享到', '收藏',
            '评论', '点赞', '相关阅读', '责任编辑', '来源：', '文章导航', '上一篇', '下一篇',
            'PC', 'English',
        ]

        # ========== 第1步：删除图片 ==========
        content = re.sub(r'!\[\]\(https?://[^)]+\)', '', content)
        content = re.sub(r'!\[[^\]]*\]\(https?://[^)]+\)', '', content)

        # ========== 第2步：删除链接格式 ==========
        content = re.sub(r'\[([^\]]*)\]\(https?://[^)]+\)', r'\1', content)
        content = re.sub(r'\[([^\]]*)\]\((/[^)]+)\)', r'\1', content)

        # ========== 第3步：清理URL路径 ==========
        content = re.sub(r'https://www\.cas\.cn/\.\./', 'https://www.cas.cn/', content)
        content = content.replace('../../', '/')

        # ========== 第4步：删除HTML标签 ==========
        content = re.sub(r'<[^>]+>', '', content)

        # ========== 第5步：删除JavaScript ==========
        content = re.sub(r'javascript:[^;\s]+', '', content)
        content = re.sub(r'onclick\s*=\s*"[^"]*"', '', content)

        # ========== 第6步：处理整行导航模式 ==========
        # 模式: "* 首页\n* 组织机构\n* 科学研究" 这类连续的导航列表
        lines = content.split('\n')
        cleaned_lines = []
        skip_next = 0  # 跳过接下来N行（处理连续导航列表）

        for i, line in enumerate(lines):
            stripped = line.strip()

            # 跳过已标记的需要跳过的行
            if skip_next > 0:
                skip_next -= 1
                continue

            # ===== 检测整行都是导航的情况 =====

            # 注意：不再使用 / 分隔检测，因为正文内容可能包含 / (如学科研究方向)

            # 1. 检测 * 或 - 开头的纯导航项列表
            # 如果当前行和接下来的几行都是 "* xxx" 格式的导航项，则全部跳过
            if stripped.startswith('* ') or stripped.startswith('- '):
                # 检查是否是连续导航项
                nav_item_count = 0
                j = i
                while j < len(lines):
                    next_stripped = lines[j].strip()
                    if next_stripped.startswith('* ') or next_stripped.startswith('- '):
                        # 检查这一项是否是导航关键字
                        item_text = next_stripped[2:].strip()
                        if any(item_text.startswith(kw) or item_text == kw for kw in nav_keywords):
                            nav_item_count += 1
                            j += 1
                        else:
                            break
                    elif not next_stripped:  # 空行，继续检查
                        j += 1
                    else:
                        break

                # 如果连续3个以上导航项，整段跳过
                if nav_item_count >= 3:
                    skip_next = nav_item_count - 1
                    continue

            # ===== 检测单个导航关键字匹配 =====

            # 检查是否以导航关键字开头
            starts_with_nav = any(
                stripped == kw or stripped.startswith(kw + ' ') or stripped.startswith(kw + '\n')
                for kw in nav_keywords
            )

            if starts_with_nav:
                # 额外检查：如果行中包含的内容主要是导航关键字，长度较短，则跳过
                nav_count_in_line = sum(1 for kw in nav_keywords if kw in stripped)
                if nav_count_in_line >= 2 or len(stripped) < 30:
                    continue

            # ===== 通用过滤规则 =====

            # 跳过空行
            if not stripped:
                continue
            if stripped in ['*', '>', '', ' ', '　']:
                continue

            # 纯符号或纯数字行跳过
            pure_symbol = re.match(r'^[\*#\-\>\s\d\.\,\;\:]+$', stripped)
            if pure_symbol and len(stripped) < 10:
                continue

            # 跳过URL行
            if stripped.startswith('http://') or stripped.startswith('https://'):
                continue

            # 跳过纯标点符号行
            if re.match(r'^[\*\-\>\s\.;:,，。、]+$', stripped) and len(stripped) < 5:
                continue

            # 检查段落中是否包含过多导航关键字（可能整段都是导航）
            nav_count_in_para = sum(1 for kw in nav_keywords if kw in stripped)
            if nav_count_in_para >= 4 and len(stripped) < 200:
                continue

            # 清理行内多余空格
            cleaned_line = ' '.join(stripped.split())

            # 只保留有实际内容的段落
            if len(cleaned_line) >= 3:
                cleaned_lines.append(cleaned_line)

        # ========== 第7步：长段落按句子分割 ==========
        paragraphs = []
        for line in cleaned_lines:
            if len(line) > 200:
                sentences = re.split(r'([。！？])', line)
                for i in range(0, len(sentences) - 1, 2):
                    if i + 1 < len(sentences):
                        sentence = sentences[i] + sentences[i + 1]
                        if len(sentence) > 10:
                            paragraphs.append(sentence)
            else:
                paragraphs.append(line)

        # ========== 第8步：合并并清理 ==========
        cleaned_content = '\n\n'.join(paragraphs)
        cleaned_content = re.sub(r'\n{3,}', '\n\n', cleaned_content)

        # ========== 第9步：最终清理段落中的残留导航项 ==========
        for kw in nav_keywords:
            # 移除段落开头的中文导航项（以 * 或 - 开头）
            cleaned_content = re.sub(rf'^[\*\-]\s*{re.escape(kw)}\s*', '', cleaned_content)
            # 移除段落中间的导航项
            cleaned_content = re.sub(rf'\s+{re.escape(kw)}\s*[,，]?\s*', ' ', cleaned_content)

        return cleaned_content.strip()

    def _extract_basic_info_from_content(self, content: str) -> dict:
        """
        从内容中提取基本信息（作者、时间等）

        Returns:
            dict: { published_at, author }
        """
        result = {
            "published_at": None,
            "author": None,
        }

        lines = content.split('\n')

        for line in lines:
            # 匹配时间：20XX年XX月XX日 或 20XX-XX-XX
            if not result["published_at"]:
                date_match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', line)
                if date_match:
                    result["published_at"] = f"{date_match.group(1)}-{date_match.group(2).zfill(2)}-{date_match.group(3).zfill(2)}"

                date_match2 = re.search(r'(\d{4})-(\d{2})-(\d{2})', line)
                if date_match2 and not result["published_at"]:
                    result["published_at"] = f"{date_match2.group(1)}-{date_match2.group(2)}-{date_match2.group(3)}"

            # 匹配作者：作者：XXX 或 作者 XXX
            if not result["author"]:
                author_match = re.search(r'作者[：:]\s*(.{2,10})', line)
                if author_match:
                    result["author"] = author_match.group(1).strip()
                else:
                    author_match2 = re.search(r'责任编辑[：:]\s*(.{2,10})', line)
                    if author_match2:
                        result["author"] = author_match2.group(1).strip()

            # 匹配来源：来源：XXX
            source_match = re.search(r'来源[：:]\s*([^\s\n]+)', line)
            if source_match and not result["author"]:
                result["author"] = source_match.group(1).strip()

        return result

    async def _extract_metadata_with_llm(self, title: str, content: str) -> dict:
        """
        使用 LLM 提取文章元信息

        Returns:
            dict: { published_at, author, summary, keywords }
        """
        try:
            llm = self._get_llm_service()

            # 先清理内容
            cleaned_content = self._clean_html_content(content)
            basic_info = self._extract_basic_info_from_content(cleaned_content)

            # 构建提示词 - 更加精确的提取要求
            prompt = f"""你是一个专业的文章分析专家。请仔细分析以下文章内容，提取准确的信息。

文章标题：{title}

文章内容（已清理无意义字符）：
{cleaned_content[:4000]}

提取要求：
1. published_at：发布时间，只返回日期格式 YYYY-MM-DD，精确到日
2. author：作者/来源，如果文章没有明确作者，返回来源网站名称（如"中国科学院"）
3. summary：内容摘要，100-200字，概括文章核心内容
4. keywords：关键字标签，从文章中提取3-5个核心关键词

请直接返回 JSON，不要任何解释文字：
{{"published_at":"YYYY-MM-DD","author":"作者名","summary":"摘要...","keywords":["关键词1","关键词2","关键词3"]}}"""

            # 调用 LLM（非流式）
            response = await llm.non_stream_chat(
                model_id="",
                messages=[{"role": "user", "content": prompt}],
            )

            # 解析 JSON 响应
            if response and not response.startswith("[错误]"):
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    try:
                        metadata = json.loads(json_match.group())
                        return {
                            "published_at": metadata.get("published_at") or basic_info.get("published_at") or "",
                            "author": metadata.get("author") or basic_info.get("author") or "",
                            "summary": metadata.get("summary") or self._generate_fallback_summary(cleaned_content),
                            "keywords": metadata.get("keywords") or [],
                        }
                    except json.JSONDecodeError:
                        logger.warning("JSON 解析失败，使用备用方案")
                        pass

            # 如果LLM解析失败，使用备用提取
            logger.warning(f"LLM 元信息提取失败，使用备用方案")
            return {
                "published_at": basic_info.get("published_at") or "",
                "author": basic_info.get("author") or "",
                "summary": self._generate_fallback_summary(cleaned_content),
                "keywords": self._extract_keywords_from_content(cleaned_content),
            }

        except Exception as e:
            logger.error(f"LLM 元信息提取异常: {e}")
            return {
                "published_at": None,
                "author": None,
                "summary": self._generate_fallback_summary(content) if content else None,
                "keywords": []
            }

    def _generate_fallback_summary(self, content: str) -> str:
        """
        生成备用摘要 - 从内容开头提取前几句完整的话
        """
        if not content:
            return ""

        # 清理内容
        content = re.sub(r'\s+', ' ', content).strip()

        # 尝试按句子分割（中文句号）
        sentences = re.split(r'([。！？])', content)

        # 合并句子和句号
        merged = []
        for i in range(0, len(sentences) - 1, 2):
            if i + 1 < len(sentences):
                merged.append(sentences[i] + sentences[i + 1])

        # 取前 2-3 句作为摘要
        summary_parts = []
        char_count = 0
        for sentence in merged:
            if char_count + len(sentence) > 200:
                break
            summary_parts.append(sentence.strip())
            char_count += len(sentence)

        if summary_parts:
            return ''.join(summary_parts)

        # 如果没有完整的句子，取前 200 字
        return content[:200] + "..."

    def _extract_keywords_from_content(self, content: str) -> List[str]:
        """
        从内容中提取关键词 - 基于词频分析
        """
        if not content or len(content) < 50:
            return []

        # 简单的关键词提取：查找重复出现的短语
        # 这里用空格分割英文单词，找出现次数多的
        words = re.findall(r'[一-龥]{2,4}', content)  # 2-4个中文字

        # 统计词频
        word_count = {}
        for word in words:
            word_count[word] = word_count.get(word, 0) + 1

        # 过滤常见停用词
        stop_words = {'的是', '是一', '可以', '我们', '这个', '这些', '为了', '通过', '并且', '或者', '以及'}

        # 取出现次数 >= 2 的词
        keywords = [w for w, c in word_count.items() if c >= 2 and w not in stop_words]

        # 按频率排序，取前 5 个
        keywords.sort(key=lambda x: word_count[x], reverse=True)
        return keywords[:5]

    def _extract_basic_metadata(self, content: str) -> dict:
        """
        尝试从内容中提取基本元信息（备用方案，不依赖 LLM）
        """
        result = {
            "published_at": None,
            "author": None,
        }

        # 简单模式匹配发布时间
        date_patterns = [
            r'(\d{4}年\d{1,2}月\d{1,2}日)',
            r'(\d{4}-\d{2}-\d{2})',
            r'(\d{4}/\d{2}/\d{2})',
        ]
        for pattern in date_patterns:
            match = re.search(pattern, content[:500])
            if match:
                result["published_at"] = match.group(1)
                break

        return result

    def _extract_published_date_from_html(self, html: str, url: str = "") -> Optional[str]:
        """
        从 HTML 多源提取发布日期，优先级：
        1. JSON-LD (Schema.org NewsArticle)
        2. Meta 标签 (article:published_time, datePublished, og:article:published_time)
        3. <time> 元素中的 datetime 属性
        4. 特定 class/id 的日期容器（中科院等国内网站常见模式）
        5. 文章内容区域的日期文本（如 "2026年6月27日"）

        Args:
            html: 网页 HTML
            url: 网页 URL（用于日志记录）

        Returns:
            str: 规范化的日期字符串 YYYY-MM-DD，或 None
        """
        from bs4 import BeautifulSoup

        try:
            soup = BeautifulSoup(html, 'lxml')

            # 1. JSON-LD（最权威的来源）
            date_str = self._extract_date_from_jsonld(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从 JSON-LD 提取到日期: {normalized}")
                    return normalized

            # 2. Meta 标签
            date_str = self._extract_date_from_meta(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从 Meta 标签提取到日期: {normalized}")
                    return normalized

            # 3. <time> 元素（优先找 article/post/main 等内容区的 time）
            date_str = self._extract_date_from_time_element(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从 <time> 元素提取到日期: {normalized}")
                    return normalized

            # 4. 特定 class/id 的日期容器（国内政府/科研网站常见模式）
            date_str = self._extract_date_from_domestic_patterns(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从国内网站模式提取到日期: {normalized}")
                    return normalized

            # 5. 从内容中的日期文本提取（常见格式）
            date_str = self._extract_date_from_content_text(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从内容文本提取到日期: {normalized}")
                    return normalized

            # 6. 扫描整个页面找最明显的日期
            date_str = self._extract_date_from_page_scan(soup)
            if date_str:
                normalized = self._normalize_date(date_str)
                if normalized:
                    scrape_logger.debug(f"从页面扫描提取到日期: {normalized}")
                    return normalized

            return None

        except Exception as e:
            scrape_logger.debug(f"日期提取失败: {e}")
            return None

    def _extract_date_from_jsonld(self, soup: "BeautifulSoup") -> Optional[str]:
        """从 JSON-LD 提取日期"""
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                # 处理单一对象
                if isinstance(data, dict):
                    if data.get('datePublished'):
                        return data['datePublished']
                    # Schema.org NewsArticle 格式
                    if data.get('dateCreated'):
                        return data['dateCreated']
                # 处理数组
                elif isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            if item.get('datePublished'):
                                return item['datePublished']
                            if item.get('dateCreated'):
                                return item['dateCreated']
            except Exception:
                continue
        return None

    def _extract_date_from_meta(self, soup: "BeautifulSoup") -> Optional[str]:
        """从 Meta 标签提取日期"""
        selectors = [
            {'property': 'article:published_time'},
            {'property': 'datePublished'},
            {'name': 'publishdate'},
            {'name': 'date'},
            {'property': 'og:article:published_time'},
        ]
        for attrs in selectors:
            tag = soup.find('meta', attrs=attrs)
            if tag and tag.get('content'):
                return tag['content']
        return None

    def _extract_date_from_time_element(self, soup: "BeautifulSoup") -> Optional[str]:
        """从 <time> 元素提取日期"""
        # 优先找主内容区的 time 标签（带 class 或 id 的）
        content_tags = soup.find_all(['article', 'main', 'div'], class_=lambda x: x and any(k in str(x).lower() for k in ['article', 'content', 'post', 'main', 'entry']))
        for container in content_tags:
            time_tag = container.find('time', datetime=True)
            if time_tag:
                datetime_val = time_tag.get('datetime', '')
                if datetime_val:
                    return datetime_val

        # 找所有带 datetime 属性的 time 标签
        for time_tag in soup.find_all('time', datetime=True):
            datetime_val = time_tag.get('datetime', '')
            if datetime_val:
                return datetime_val

        # 找文本内容是日期的 time 标签
        for time_tag in soup.find_all('time'):
            text = time_tag.get_text(strip=True)
            if re.search(r'\d{4}[-/年]', text):
                return text

        return None

    def _extract_date_from_content_text(self, soup: "BeautifulSoup") -> Optional[str]:
        """
        从文章内容区域提取日期文本
        通常在标题下方或文章开头会有发布日期
        """
        # 查找常见的日期容器
        date_containers = soup.find_all(['div', 'span', 'p', 'font'],
            class_=lambda x: x and any(k in str(x).lower() for k in ['date', 'time', 'pub', 'publish', 'create', 'update']))

        for container in date_containers:
            text = container.get_text(strip=True)
            # 匹配中文日期格式
            match = re.search(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', text)
            if match:
                return f"{match.group(1)}-{match.group(2).zfill(2)}-{match.group(3).zfill(2)}"

            # 匹配 YYYY-MM-DD 格式
            match = re.search(r'(\d{4})-(\d{2})-(\d{2})', text)
            if match:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

            # 匹配 YYYY/MM/DD 格式
            match = re.search(r'(\d{4})/(\d{2})/(\d{2})', text)
            if match:
                return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"

        return None

    def _extract_date_from_domestic_patterns(self, soup: "BeautifulSoup") -> Optional[str]:
        """
        从国内网站的常见 DOM 模式提取日期
        例如中科院网站、政府网站等

        Returns:
            str: 日期字符串或 None
        """
        # 国内网站常见的日期容器 class/id 模式
        date_patterns = [
            # 常见 class 名
            {'class': lambda x: x and any(k in str(x).lower() for k in [
                'date', 'time', 'pub', 'publish', 'create', 'update', 'info', 'tips', 'source'
            ])},
            # 常见 id 名
            {'id': lambda x: x and any(k in str(x).lower() for k in [
                'date', 'time', 'pub', 'publish', 'create', 'update'
            ])},
        ]

        for pattern in date_patterns:
            elements = soup.find_all(['div', 'span', 'p', 'font', 'td', 'li'], **pattern)
            for elem in elements:
                text = elem.get_text(strip=True)
                # 跳过太长的文本
                if len(text) > 100:
                    continue
                # 匹配各种日期格式
                for regex, fmt in [
                    (r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日', '%s-%s-%s'),
                    (r'(\d{4})-(\d{2})-(\d{2})', '%s-%s-%s'),
                    (r'(\d{4})/(\d{2})/(\d{2})', '%s-%s-%s'),
                    (r'(\d{4})\.(\d{2})\.(\d{2})', '%s-%s-%s'),
                ]:
                    match = re.search(regex, text)
                    if match:
                        if fmt == '%s-%s-%s':
                            groups = match.groups()
                            # 检查是否是有效的日期
                            try:
                                year, month, day = groups
                                month = month.lstrip('0') or '1'
                                day = day.lstrip('0') or '1'
                                y, m, d = int(year), int(month), int(day)
                                if 2000 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                                    return f"{y}-{int(month):02d}-{int(day):02d}"
                            except:
                                pass

        # 查找标题附近的日期（通常在标题后面紧跟日期）
        # 常见模式：标题 + 日期 在同一个容器内
        title_container = soup.find(['h1', 'h2', 'h3', 'div', 'article'],
            class_=lambda x: x and any(k in str(x).lower() for k in ['title', 'head', 'article-title', 'news-title']))
        if title_container:
            # 查看标题容器的父元素或相邻元素
            parent = title_container.parent
            if parent:
                # 查找父容器中的日期
                date_elements = parent.find_all(['span', 'div', 'font', 'p'],
                    class_=lambda x: x and any(k in str(x).lower() for k in ['date', 'time', 'pub']))
                for elem in date_elements:
                    text = elem.get_text(strip=True)
                    match = re.search(r'(\d{4})\s*[-年/]\s*(\d{1,2})\s*[-月/]\s*(\d{1,2})', text)
                    if match:
                        return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"

        return None

    def _extract_date_from_page_scan(self, soup: "BeautifulSoup") -> Optional[str]:
        """
        扫描整个页面寻找最明显的日期
        通常发布日期会突出显示

        Returns:
            str: 日期字符串或 None
        """
        # 寻找带特定样式的日期元素
        style_date_patterns = [
            # 常见的内联样式日期
            {'style': lambda x: x and 'color' in str(x)},
        ]

        # 查找文章区域（通常在 main, article, content 等标签内）
        content_areas = soup.find_all(['article', 'main', 'div'],
            class_=lambda x: x and any(k in str(x).lower() for k in [
                'article', 'content', 'main', 'detail', 'text', 'show', 'news'
            ]))

        for area in content_areas[:3]:  # 只检查前3个匹配的区域
            # 在内容区域内查找日期
            text = area.get_text()
            if len(text) < 5000:  # 确保是有效的内容区域
                # 优先找文章标题后的日期模式
                # 格式：2026年6月27日 或 2026-06-27 或 2026.06.27
                for regex in [
                    r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日',
                    r'发布时间[：:]\s*(\d{4})[-年](\d{1,2})[-月](\d{1,2})',
                    r'发布日期[：:]\s*(\d{4})[-年](\d{1,2})[-月](\d{1,2})',
                    r'(\d{4})[-/.](\d{2})[-/.](\d{2})',
                ]:
                    match = re.search(regex, text)
                    if match:
                        groups = match.groups()
                        try:
                            return f"{int(groups[0])}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                        except:
                            pass

        return None

    def _extract_date_from_url(self, url: str) -> Optional[str]:
        """
        从 URL 提取日期
        支持多种 URL 日期格式：
        - t20260627_id.shtml 文件名格式（如 https://xxx/202606/t20260627_8234968.html）
        - /2026/06/27/ 目录格式
        - /20260627/ 紧凑目录格式
        """
        # 模式1: t20260627 或 t20260629_xxx 格式（最常见的中科院网站格式）
        match = re.search(r'/t(\d{8})_\d+\.', url)
        if match:
            date_str = match.group(1)
            return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

        # 模式2: /2026/06/27/ 或 /2026/6/27/ 目录格式
        match = re.match(r'.*?/(\d{4})/(\d{1,2})/(\d{1,2})/', url)
        if match:
            year, month, day = match.groups()
            return f"{year}-{int(month):02d}-{int(day):02d}"

        # 模式3: /202606/ 目录 + 文件 /xxx.html（没有日期目录）
        match = re.search(r'/(\d{6})/[^/]+\.s?html?', url)
        if match:
            date_str = match.group(1)
            # 检查是否是有效的日期
            try:
                year = int(date_str[:4])
                month = int(date_str[4:6])
                if 2000 <= year <= 2100 and 1 <= month <= 12:
                    return f"{date_str[:4]}-{date_str[4:6]}-01"
            except:
                pass

        # 模式4: /20260627/ 紧凑格式
        match = re.match(r'.*?/(\d{4})(\d{2})(\d{2})/', url)
        if match:
            year, month, day = match.groups()
            return f"{year}-{month}-{day}"

        # 模式5: /202606/ 年月目录
        match = re.search(r'/(\d{4})(\d{2})/', url)
        if match:
            date_str = match.group(0).strip('/')
            try:
                year = int(date_str[:4])
                month = int(date_str[4:6])
                if 2000 <= year <= 2100 and 1 <= month <= 12:
                    return f"{date_str[:4]}-{date_str[4:6]}-01"
            except:
                pass

        return None

    def _normalize_date(self, date_str: str) -> Optional[str]:
        """将各种日期格式规范化为 YYYY-MM-DD"""
        if not date_str:
            return None

        # ISO 格式预处理：去掉时间和时区
        date_str = date_str.split('T')[0].split('+')[0].strip()
        date_str = date_str.split('Z')[0].strip()

        formats = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%Y年%m月%d日",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _filter_by_date(
        self,
        articles: List["ScrapedResult"],
        date_range: Optional[str] = None,
        custom_range: Optional[dict] = None
    ) -> List["ScrapedResult"]:
        """
        根据日期范围过滤文章

        Args:
            articles: 文章列表
            date_range: 预设选项 ("today", "week", "month")
            custom_range: 自定义日期范围 {"start_date": date, "end_date": date}

        Returns:
            List[ScrapedResult]: 过滤后的文章列表
        """
        scrape_logger.info(f"日期过滤开始 | date_range={date_range}, custom_range={custom_range}, 文章数={len(articles)}")

        if not date_range and not custom_range:
            scrape_logger.info("日期过滤跳过：无过滤条件，返回全部")
            return articles  # 无过滤条件，返回全部

        # 计算目标日期范围
        today = date.today()

        if date_range:
            if date_range == "today":
                start_date = today
                end_date = today
            elif date_range == "week":
                start_date = today - timedelta(days=7)
                end_date = today
            elif date_range == "month":
                start_date = today - timedelta(days=30)
                end_date = today
            else:
                return articles
        elif custom_range:
            start_date = custom_range.get("start_date")
            end_date = custom_range.get("end_date")
            if not start_date:
                start_date = date(2000, 1, 1)  # 无起始日期则从最早开始
            if not end_date:
                end_date = today
        else:
            return articles

        scrape_logger.info(f"日期范围: {start_date} 至 {end_date}")

        # 过滤
        filtered = []
        filtered_count = 0
        skipped_count = 0
        no_date_count = 0

        for article in articles:
            scrape_logger.debug(f"检查文章: {article.url}, published_at={article.published_at}")

            # 没有发布日期的文章：严格模式下排除，放宽模式下保留
            if not article.published_at:
                no_date_count += 1
                # 为了时间控制生效，我们不保留无日期的文章
                # 用户设置了时间范围，说明只想要确定在该范围内的文章
                scrape_logger.debug(f"文章无发布日期，跳过: {article.url}")
                skipped_count += 1
                continue

            try:
                pub_date = self._parse_date_to_date(article.published_at)
                if pub_date:
                    if start_date <= pub_date <= end_date:
                        filtered.append(article)
                        filtered_count += 1
                        scrape_logger.debug(f"日期 {pub_date} 在范围内 [{start_date} ~ {end_date}]，保留: {article.title[:30]}")
                    else:
                        scrape_logger.debug(f"日期 {pub_date} 超出范围 [{start_date} ~ {end_date}]，跳过: {article.title[:30]}")
                        skipped_count += 1
                else:
                    # 无法解析日期，跳过
                    scrape_logger.warning(f"无法解析日期 '{article.published_at}'，跳过: {article.url}")
                    skipped_count += 1
            except Exception as e:
                scrape_logger.error(f"日期解析异常: {e}")
                skipped_count += 1

        scrape_logger.info(f"日期过滤完成: 总数={len(articles)}, 保留={len(filtered)}, 跳过={skipped_count}, 无日期={no_date_count}")
        return filtered

    def _parse_date_to_date(self, date_str: str) -> Optional[date]:
        """解析日期字符串为 date 对象"""
        if not date_str:
            return None

        # 先尝试直接解析 YYYY-MM-DD 格式
        try:
            return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

        # 尝试其他格式
        formats = [
            "%Y/%m/%d",
            "%Y年%m月%d日",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).date()
            except ValueError:
                continue
        return None

    def _sort_by_published_date(
        self,
        articles: List["ScrapedResult"]
    ) -> List["ScrapedResult"]:
        """
        按发布日期排序，最新的在前

        Returns:
            List[ScrapedResult]: 排序后的文章列表，无日期的文章排在最后
        """
        def get_sort_key(article: ScrapedResult) -> tuple:
            """返回排序键：(有日期标志, 日期值)"""
            if not article.published_at:
                # 无日期的文章排到最后
                return (1, datetime.min.date())
            try:
                pub_date = self._parse_date_to_date(article.published_at)
                if pub_date:
                    return (0, pub_date)  # 有日期的文章排在前
            except:
                pass
            return (1, datetime.min.date())

        # 按日期降序排序（最新的在前）
        sorted_articles = sorted(articles, key=get_sort_key, reverse=True)

        # 统计信息
        with_date = len([a for a in sorted_articles if a.published_at])
        without_date = len(sorted_articles) - with_date
        scrape_logger.info(f"排序完成: 有日期={with_date}, 无日期={without_date}")

        if sorted_articles and sorted_articles[0].published_at:
            latest = sorted_articles[0]
            scrape_logger.info(f"最新文章: {latest.title[:40]}... 日期: {latest.published_at}")

        return sorted_articles

    def _is_list_page(self, url: str, html: str, links: List[str], extracted_content: str) -> bool:
        """
        智能检测页面是否是列表页/首页（没有实质性正文内容）

        检测标准：
        1. URL 是索引页或栏目页
        2. 链接数量多但正文字数少
        3. 链接密度高

        Returns:
            bool: True 表示是列表页
        """
        from bs4 import BeautifulSoup

        url_lower = url.lower()

        # 1. URL 模式检测：索引页、栏目页
        index_patterns = [
            r'/index\.?(html?|htm|shtml)?$',
            r'/\s*$',  # 以斜杠结尾
            r'/list\.?(html?|htm|shtml)?$',
            r'/list_\d+\.?(html?|htm|shtml)?$',  # list_1.html, list_2.html
            r'/index_\d+\.?(html?|htm|shtml)?$',  # index_1.html
        ]
        for pattern in index_patterns:
            if re.search(pattern, url_lower.rstrip('/')):
                logger.info(f"URL 模式匹配列表页: {url}")
                return True

        # 如果不是索引页，再检查内容
        if not html:
            return False

        try:
            soup = BeautifulSoup(html, 'lxml')
            text = soup.get_text(separator=' ', strip=True)
            content_length = len(extracted_content) if extracted_content else 0

            # 2. 正文字数检测：少于 200 字可能是列表页
            if content_length < 200:
                # 检查是否有明显的内容区块
                has_article_content = re.search(r'[一-龥]{50,}', extracted_content or text[:500])
                if not has_article_content:
                    logger.info(f"正文字数过少({content_length})，判定为列表页")
                    return True

            # 3. 链接密度检测：链接数量多但正文短
            link_count = len(links)
            text_length = len(text)

            if link_count > 10 and content_length < 500:
                link_density = link_count / (text_length / 100) if text_length > 0 else 0
                if link_density > 5:  # 每 100 字超过 5 个链接
                    logger.info(f"链接密度过高({link_density:.1f})，判定为列表页")
                    return True

        except Exception as e:
            logger.warning(f"列表页检测异常: {e}")

        return False

    async def scrape(self, url: str, options: Optional[ScrapeOptions] = None) -> ScrapedResult:
        """
        爬取单个网页

        Args:
            url: 网页 URL
            options: 爬取选项

        Returns:
            ScrapedResult: 爬取结果
        """
        if options is None:
            options = ScrapeOptions()

        result = ScrapedResult(url=url)

        try:
            crawl_config = self._create_crawl_config(options)

            # 开始爬取日志
            scrape_logger.log_scrape_start(url, "single")

            async with AsyncWebCrawler(config=self._browser_config) as crawler:
                logger.info(f"开始爬取: {url}")
                crawl_result = await crawler.arun(url=url, config=crawl_config)

                if crawl_result.success:
                    raw_html = crawl_result.html or ""

                    # 1. 识别网站类型
                    profile = self._classifier.classify(url, raw_html)
                    logger.info(f"网站类型: {profile.website_type.value}, 推荐提取器: {profile.recommended_extractor}")

                    # 提取链接（优先从 HTML 直接解析，处理相对路径）
                    html_links = self._extract_links_from_html(raw_html, url)

                    # 如果 crawl4ai 返回了 links，合并（去重）
                    if crawl_result.links:
                        raw_links = crawl_result.links.get("internal", [])[:50]
                        for link in raw_links:
                            if isinstance(link, dict):
                                href = link.get("href", "")
                            elif isinstance(link, str):
                                href = link
                            else:
                                href = str(link)
                            if href:
                                # 转换为绝对路径后加入
                                from urllib.parse import urljoin
                                if href.startswith('http'):
                                    if href not in html_links:
                                        html_links.append(href)
                                else:
                                    abs_url = urljoin(url, href)
                                    if abs_url not in html_links:
                                        html_links.append(abs_url)

                    result.links = html_links

                    # 2. 使用智能提取器提取正文
                    extracted = smart_extract(raw_html, url, profile)

                    if extracted.is_valid():
                        extracted_content = extracted.text or extracted.content
                        cleaned_content = self._clean_html_content(extracted_content)
                    else:
                        extracted_content = crawl_result.markdown or ""
                        cleaned_content = self._clean_html_content(extracted_content)

                    # 3. 智能检测是否是列表页
                    is_list = self._is_list_page(url, raw_html, html_links, cleaned_content)

                    if is_list:
                        # 列表页：只返回标题和链接，不提取正文
                        logger.info(f"检测为列表页，跳过正文提取: {url}")
                        result.title = crawl_result.metadata.get("title", extracted.title or "")
                        result.content = ""  # 列表页不保存正文
                        result.word_count = 0
                        result.html = raw_html
                        result.status = "success"
                        scrape_logger.log_scrape_result(url, "success", 0, result.title)
                        return result

                    # 文章页：正常提取正文
                    result.title = extracted.title or crawl_result.metadata.get("title", "")
                    result.content = cleaned_content
                    result.html = raw_html
                    result.word_count = len(result.content.replace("\n", "").replace(" ", ""))

                    # 使用 LLM 提取元信息
                    if options.extract_metadata and result.content:
                        logger.info(f"开始提取元信息: {url}")
                        metadata = await self._extract_metadata_with_llm(result.title, result.content)
                        result.published_at = metadata.get("published_at")
                        result.author = metadata.get("author")
                        result.summary = metadata.get("summary")
                        result.keywords = metadata.get("keywords", [])
                        logger.info(f"元信息提取完成: author={result.author}, keywords={result.keywords}")
                    else:
                        # 备用：尝试从内容中提取基本元信息
                        basic_meta = self._extract_basic_metadata(result.content)
                        result.published_at = basic_meta.get("published_at")
                        result.author = basic_meta.get("author")

                    result.status = "success"
                    logger.info(f"爬取成功: {url}, 字数: {result.word_count}")
                    # 记录爬取结果到日志文件
                    scrape_logger.log_scrape_result(url, "success", result.word_count, result.title)
                else:
                    result.status = "error"
                    result.error_message = crawl_result.error_message or "爬取失败"
                    logger.error(f"爬取失败: {url}, 错误: {result.error_message}")
                    scrape_logger.log_scrape_result(url, "error", 0)

        except asyncio.TimeoutError:
            result.status = "error"
            result.error_message = "爬取超时"
            logger.error(f"爬取超时: {url}")
            scrape_logger.log_scrape_result(url, "timeout", 0)

        except Exception as e:
            result.status = "error"
            result.error_message = str(e)
            logger.error(f"爬取异常: {url}, 错误: {e}")
            scrape_logger.log_scrape_result(url, "exception", 0)

        return result

    async def scrape_batch(
        self,
        urls: List[str],
        options: Optional[ScrapeOptions] = None,
        max_concurrent: int = 3
    ) -> List[ScrapedResult]:
        """
        批量爬取多个网页

        Args:
            urls: URL 列表
            options: 爬取选项
            max_concurrent: 最大并发数

        Returns:
            List[ScrapedResult]: 爬取结果列表
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def scrape_with_limit(url: str) -> ScrapedResult:
            async with semaphore:
                return await self.scrape(url, options)

        tasks = [scrape_with_limit(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(ScrapedResult(
                    url=urls[i],
                    status="error",
                    error_message=str(result)
                ))
            else:
                processed_results.append(result)

        return processed_results

    async def _extract_article_links_with_llm(
        self,
        page_url: str,
        page_title: str,
        content: str,
        all_links: List[str],
        base_url: str
    ) -> List[str]:
        """
        使用 LLM 识别文章链接（专门识别二级页面中的文章）

        Returns:
            List[str]: 识别出的文章链接
        """
        try:
            llm = self._get_llm_service()

            # 先用规则过滤出可能的文章链接
            filtered_links = self._filter_article_links_heuristic(all_links, base_url, content)

            if len(filtered_links) > 50:
                filtered_links = filtered_links[:50]

            prompt = f"""你是一个新闻文章识别专家。请从以下链接列表中，识别出真正的新闻文章详情页链接。

页面标题：{page_title}
页面地址：{page_url}

链接列表（每行一个）：
{chr(10).join(filtered_links)}

识别规则（严格遵守）：
1. 文章详情页特征：
   - URL 通常包含日期目录（如 /202606/）或特定ID
   - 常见格式：/yyyyMM/ 或 /yyyyMMdd/ 目录下的 .shtml 文件
   - 链接末尾通常是完整的文章标题（中文或英文）
2. 必须排除的链接类型：
   - 栏目页/频道页：如 /xw/、/kyjz/、/zhxx/（这些是栏目入口，不是文章）
   - 导航菜单：首页、标题栏链接、面包屑父级
   - 列表页中的"更多"按钮、分页链接
   - 登录注册、关于我们、联系我们等页面
   - 其他网站的外部链接
3. 正确的文章链接示例：
   - /yw/202606/t20260618_5112884.shtml ✅
   - /kx/202506/P02025061952345678.shtml ✅
   - /info/P020210615123456789.shtml ✅
4. 错误链接示例：
   - /yw/ ❌ (栏目页)
   - /kyjz/ ❌ (栏目页)
   - /index.html ❌ (首页)
   - /newspaper/ ❌ (频道页)

请只返回真正的文章详情页链接，按 JSON 格式：
{{
    "article_links": ["完整URL1", "完整URL2", ...],
    "reason": "简要说明"
}}

只返回 JSON，不要有其他内容。
"""

            response = await llm.non_stream_chat(
                model_id="",
                messages=[{"role": "user", "content": prompt}],
            )

            if response and not response.startswith("[错误]"):
                json_match = re.search(r'\{[\s\S]*\}', response)
                if json_match:
                    data = json.loads(json_match.group())
                    links = data.get("article_links", [])
                    logger.info(f"LLM 识别出 {len(links)} 个文章链接")

                    # 确保链接是完整的URL，并排除原始 URL
                    final_links = []
                    from urllib.parse import urljoin
                    for link in links:
                        if link.startswith('http'):
                            abs_url = link
                        else:
                            abs_url = urljoin(base_url, link)

                        # 排除原始 URL 本身（列表页/首页）
                        # 排除以 index 结尾的页面
                        is_index_page = re.search(r'/index\.?(html?|htm|shtml)?$', abs_url.lower())
                        is_original_url = abs_url.rstrip('/').lower() == base_url.rstrip('/').lower()

                        if abs_url and not is_original_url and not is_index_page:
                            final_links.append(abs_url)

                    logger.info(f"过滤后剩余 {len(final_links)} 个有效文章链接")
                    return final_links

            logger.warning("LLM 链接识别失败，使用基于规则的过滤")
            # 过滤后也排除原始 URL
            result = [l for l in filtered_links[:20] if l.rstrip('/').lower() != base_url.rstrip('/').lower()]
            return result

        except Exception as e:
            logger.error(f"LLM 链接识别异常: {e}")
            return self._filter_article_links_heuristic(all_links, base_url, content)

    def _filter_article_links_heuristic(self, links: List[str], base_url: str, content: str) -> List[str]:
        """
        基于启发式规则过滤文章链接
        重点识别带日期目录的文章详情页（如 /202606/t20260618_xxx.shtml 或 .html）

        Returns:
            List[str]: 可能的文章链接
        """
        from urllib.parse import urlparse, urljoin, urlunparse

        try:
            parsed = urlparse(base_url)
            domain = parsed.netloc
        except:
            domain = ""

        article_links = []
        skip_patterns = [
            'login', 'register', 'signup', 'signin',  # 登录注册
            'about', 'contact', 'about-us', 'contact-us',  # 关于联系
            'search', 'query', 'search.', 'search/',  # 搜索
            'user', 'profile', 'account', 'member',  # 用户相关
            'comment', 'reply', 'reply-to', 'feedback',  # 评论反馈
            '/tag/', '/category/', '/topic/',  # 分类标签
            '/page/', '?page=', '&page=',  # 分页
            'index.html', 'index.htm', 'index.shtml',  # 首页
            '/photo/', '/video/', '/audio/',  # 媒体页
            '/news/',  # 频道页（不是文章详情页）
            'javascript:', '#', 'mailto:', 'tel:',  # 特殊链接
        ]

        # 文章链接特征模式（优先识别）
        article_patterns = [
            # 带年份目录的链接：如 /202606/ 或 /2025/ 等（真正的文章目录）
            r'/\d{6}/',  # /202606/ (6位数字目录)
            # 类似 t20260618_xxx 的格式（日期格式文章ID）
            r'/t\d{8}_\d+\.',  # /t20260618_8234070.html 或 .shtml
            # 类似 P020210615... 的ID格式
            r'/P0\d+',
            # 常见的文章详情URL关键词
            r'/article',
            r'/content',
            r'/info',
            r'/detail',
            # .shtml 或 .html 结尾的文件（文章详情页）
            r'\.shtml',
            r'\.html',
            r'\.htm',
            # 问号参数格式
            r'\?id=\d+',
            r'&id=\d+',
            r'/id/\d+',
        ]

        for link in links:
            # 排除空链接和特殊链接
            if not link:
                continue
            link_lower = link.lower()
            if link_lower.startswith('#') or link_lower.startswith('javascript:'):
                continue

            # 处理相对路径：将 ./xxx 或 ../xxx 转换为绝对路径
            normalized_link = link
            if link.startswith('./') or link.startswith('../'):
                # 使用 urljoin 将相对路径转换为绝对路径
                normalized_link = urljoin(base_url, link)
                # 清理 ./ 前缀（urljoin 不会自动清理）
                normalized_link = normalized_link.replace(base_url.rstrip('/') + '/./', base_url.rstrip('/') + '/')

            # 检查是否是外部链接
            if domain:
                try:
                    parsed_link = urlparse(normalized_link)
                    if parsed_link.netloc and parsed_link.netloc != domain:
                        continue
                except:
                    continue

            # 排除明显不是文章的链接
            is_skip = False
            normalized_lower = normalized_link.lower()
            for pattern in skip_patterns:
                if pattern in normalized_lower:
                    is_skip = True
                    break
            if is_skip:
                continue

            # 必须检查是否符合文章链接模式
            is_article = False
            for pattern in article_patterns:
                if re.search(pattern, normalized_lower):
                    is_article = True
                    break

            if is_article:
                article_links.append(normalized_link)

        # 去重
        article_links = list(set(article_links))

        # 排除原始 URL 和索引页
        base_url_normalized = base_url.rstrip('/').lower()
        filtered_links = []
        for link in article_links:
            link_normalized = link.rstrip('/').lower()
            is_original_url = link_normalized == base_url_normalized
            is_index_page = re.search(r'/index\.?(html?|htm|shtml)?$', link_normalized)

            if not is_original_url and not is_index_page:
                filtered_links.append(link)

        # 按URL模式排序：带年份目录的优先，其次是 t{date}_{id} 格式
        def sort_key(url):
            url_lower = url.lower()
            if re.search(r'/\d{6}/', url_lower):
                return 0  # 带年份目录的最优先
            elif re.search(r'/t\d{8}_\d+\.', url_lower):  # t20260618_xxx 格式
                return 1
            elif '.shtml' in url_lower:
                return 2
            elif '/P0' in url_lower:
                return 3
            elif '.html' in url_lower:
                return 4
            else:
                return 5

        filtered_links.sort(key=sort_key)

        # 限制数量
        return filtered_links[:30]

    def _extract_links_from_html(self, html: str, base_url: str) -> List[str]:
        """
        从 HTML 直接提取所有链接（处理相对路径）

        Returns:
            List[str]: 提取的链接列表（已转为绝对路径）
        """
        from bs4 import BeautifulSoup
        from urllib.parse import urljoin

        links = []

        try:
            soup = BeautifulSoup(html, 'lxml')

            # 移除 script 和 style 标签（避免提取到注释中的链接）
            for tag in soup(['script', 'style', 'noscript']):
                tag.decompose()

            # 查找所有 a 标签
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href'].strip()

                # 跳过空链接和特殊链接
                if not href or href.startswith('#') or href.startswith('javascript:') or href.startswith('mailto:'):
                    continue

                # 转换为绝对路径
                if href.startswith('http'):
                    abs_url = href
                else:
                    abs_url = urljoin(base_url, href)

                if abs_url and abs_url not in links:
                    links.append(abs_url)

        except Exception as e:
            logger.warning(f"HTML 链接提取失败: {e}")

        return links

    async def _scrape_list_page_fast(
        self,
        url: str,
        options: ScrapeOptions
    ) -> tuple[str, str, List[str], str]:
        """
        快速爬取列表页：只获取 HTML 和标题，不提取正文内容

        Returns:
            tuple: (title, html, links, error_message)
        """
        try:
            crawl_config = self._create_crawl_config(options)

            async with AsyncWebCrawler(config=self._browser_config) as crawler:
                crawl_result = await crawler.arun(url=url, config=crawl_config)

                if crawl_result.success:
                    # 提取标题
                    title = crawl_result.metadata.get("title", "")

                    # 直接从 HTML 提取链接（处理相对路径）
                    links = self._extract_links_from_html(crawl_result.html or "", url)

                    logger.info(f"列表页快速爬取成功: {url}, 获取到 {len(links)} 个链接")
                    return title, crawl_result.html or "", links, ""
                else:
                    error = crawl_result.error_message or "爬取失败"
                    logger.error(f"列表页爬取失败: {url}, 错误: {error}")
                    return "", "", [], error

        except Exception as e:
            logger.error(f"列表页爬取异常: {e}")
            return "", "", [], str(e)

    async def deep_scrape(
        self,
        url: str,
        options: Optional[ScrapeOptions] = None,
        max_articles: int = 10,
        date_range: Optional[str] = None,
        custom_date_range: Optional[dict] = None,
        scrape_level: Optional[str] = "deep",
        scrape_id: Optional[str] = None
    ) -> tuple[ScrapedResult, List[ScrapedResult]]:
        """
        深度爬取：从列表页识别文章链接，然后爬取每篇文章内容
        列表页不爬取正文内容，只提取链接

        Args:
            url: 列表页 URL
            options: 爬取选项
            max_articles: 最多爬取的文章数量
            date_range: 预设日期范围 ("today", "week", "month")
            custom_date_range: 自定义日期范围 {"start_date": date, "end_date": date}
            scrape_level: 爬取级别 ("list"=仅提取链接, "detail"=爬取直接子页面, "deep"=深度爬取)
            scrape_id: 可选的爬取ID，用于进度跟踪。如果不提供，则自动生成

        Returns:
            tuple: (列表页结果, 文章结果列表)
        """
        # 默认爬取级别
        if scrape_level is None:
            scrape_level = "deep"

        scrape_logger.info(f"深度爬取开始 | URL: {url} | 爬取级别: {scrape_level} | 日期范围: {date_range or '无'}")
        if options is None:
            options = ScrapeOptions()

        logger.info(f"开始深度爬取: {url}")
        scrape_logger.log_scrape_start(url, "deep")

        # 检查是否已取消
        self._check_cancelled()

        # 生成爬取ID用于进度跟踪（如果未提供或无效）
        import uuid
        if not scrape_id:
            scrape_id = str(uuid.uuid4())[:8]

        # 发送阶段1：正在解析列表页
        progress_manager.set_progress(scrape_id, {
            "status": "scraping",
            "stage": 1,
            "stage_name": "正在解析列表页",
            "stage_detail": f"访问 {url}",
            "current": 0,
            "total": 0,
        })

        # 1. 快速爬取列表页（只获取 HTML 和链接，不提取正文）
        list_title, list_html, list_links, list_error = await self._scrape_list_page_fast(url, options)

        # 检查是否已取消
        self._check_cancelled()

        if list_error:
            error_result = ScrapedResult(url=url, status="error", error_message=list_error)
            progress_manager.set_progress(scrape_id, {
                "status": "error",
                "stage": -1,
                "stage_name": "爬取失败",
                "stage_detail": list_error,
                "current": 0,
                "total": 0,
            })
            return error_result, []

        # 创建列表页结果（不包含 content，只有链接信息）
        list_page_result = ScrapedResult(
            url=url,
            title=list_title or "列表页",
            content="",  # 列表页不保存正文内容
            word_count=0,
            links=list_links,
            status="success"
        )

        # 发送阶段2：正在识别文章链接
        progress_manager.set_progress(scrape_id, {
            "status": "scraping",
            "stage": 2,
            "stage_name": "正在识别文章链接",
            "stage_detail": f"发现 {len(list_links)} 个链接，正在使用 AI 分析...",
            "current": 0,
            "total": 0,
        })

        # 2. 使用 LLM 识别文章链接
        article_links = await self._extract_article_links_with_llm(
            page_url=url,
            page_title=list_title or "列表页",
            content="",  # 列表页没有正文内容
            all_links=list_links,
            base_url=url
        )

        # 检查是否已取消
        self._check_cancelled()

        # 记录识别的文章链接
        scrape_logger.log_article_links(url, article_links)

        if not article_links:
            logger.warning("未识别到文章链接")
            progress_manager.set_progress(scrape_id, {
                "status": "error",
                "stage": -1,
                "stage_name": "未识别到文章链接",
                "stage_detail": "请检查URL是否正确或网站是否可访问",
                "current": 0,
                "total": 0,
            })
            return list_page_result, []

        # ========== 根据爬取级别执行不同的逻辑 ==========
        if scrape_level == "list":
            # 仅 list 级别：只提取链接，不爬取内容
            scrape_logger.info(f"爬取级别=list，仅返回链接列表，共 {len(article_links)} 个")
            progress_manager.set_progress(scrape_id, {
                "status": "completed",
                "stage": 5,
                "stage_name": "已完成",
                "stage_detail": f"识别到 {len(article_links)} 个文章链接",
                "current": len(article_links),
                "total": len(article_links),
            })
            # 返回空的文章列表（只有列表页结果）
            return list_page_result, []

        # detail 或 deep 级别：需要爬取文章正文
        # 限制文章数量（多爬取一些，日期过滤后会减少）
        article_links = article_links[:max(max_articles * 2, 50)]
        logger.info(f"将爬取 {len(article_links)} 篇文章（日期过滤前）")

        # 发送阶段3：准备爬取文章（此时有总数了）
        progress_manager.set_progress(scrape_id, {
            "status": "scraping",
            "stage": 3,
            "stage_name": "正在爬取文章",
            "stage_detail": f"已识别 {len(article_links)} 篇文章，开始批量爬取...",
            "current": 0,
            "total": len(article_links),
        })

        # 3. 批量爬取文章
        article_results = []
        semaphore = asyncio.Semaphore(3)  # 最多3个并发
        cancelled = False
        completed_count = 0
        success_count = 0

        async def scrape_article(article_url: str, index: int) -> ScrapedResult:
            nonlocal cancelled, completed_count, success_count
            async with semaphore:
                # 检查是否已取消
                if self._is_cancelled():
                    cancelled = True
                    return ScrapedResult(
                        url=article_url,
                        status="cancelled",
                        error_message="爬取已取消"
                    )

                logger.info(f"爬取文章 [{index+1}/{len(article_links)}]: {article_url}")
                # 列表页不提取元信息，加快速度
                article_options = ScrapeOptions(
                    extract_content=True,
                    fetch_html=False,
                    preserve_format=options.preserve_format,
                    max_depth=0,
                    timeout=options.timeout,
                    extract_metadata=True  # 文章页仍然提取元信息
                )
                result = await self.scrape(article_url, article_options)

                # 检查是否已取消
                if self._is_cancelled():
                    cancelled = True
                    result.status = "cancelled"
                    result.error_message = "爬取已取消"

                # 优先从 HTML 多源提取真实日期（JSON-LD、Meta、time 元素）
                # 如果 LLM 已有日期，先保留；HTML 多源提取的结果更权威
                if result.html and result.status != "cancelled":
                    html_date = self._extract_published_date_from_html(result.html, result.url)
                    if html_date:
                        old_date = result.published_at
                        result.published_at = html_date
                        logger.info(f"HTML 多源日期提取: {result.url} -> {html_date}" + (f" (LLM 生成: {old_date})" if old_date else ""))

                # 如果仍然没有有效日期，从 URL 提取日期作为回退（URL 日期通常最准确）
                if not result.published_at and result.status != "cancelled":
                    url_date = self._extract_date_from_url(result.url)
                    if url_date:
                        result.published_at = url_date
                        logger.info(f"URL 备用日期提取: {result.url} -> {url_date}")

                # 更新进度
                completed_count += 1
                if result.status == "success":
                    success_count += 1

                # 发送进度事件（使用 set_progress 确保包含 total）
                progress_manager.set_progress(scrape_id, {
                    "status": "scraping",
                    "stage": 3,
                    "stage_name": "正在爬取文章",
                    "stage_detail": f"正在爬取: {result.title[:30]}..." if result.title else f"已爬取 {completed_count}/{len(article_links)} 篇",
                    "current": completed_count,
                    "total": len(article_links),
                    "current_article": result.title,
                })

                return result

        # 并发爬取所有文章
        tasks = [scrape_article(link, i) for i, link in enumerate(article_links)]
        article_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 检查整体是否已取消
        if self._is_cancelled():
            cancelled = True

        # 处理异常结果
        final_results = []
        success_count = 0
        cancelled_count = 0
        for i, result in enumerate(article_results):
            if isinstance(result, Exception):
                final_results.append(ScrapedResult(
                    url=article_links[i],
                    status="error",
                    error_message=str(result)
                ))
            else:
                final_results.append(result)
                if result.status == "success":
                    success_count += 1
                elif result.status == "cancelled":
                    cancelled_count += 1

        # 4. 按日期过滤或排序（取消状态的文章不参与过滤）
        scrape_logger.info(f"准备处理文章: date_range={date_range}, custom_date_range={custom_date_range}, 文章数={len(final_results)}")
        has_date_filter = date_range or custom_date_range

        if has_date_filter:
            # 有日期过滤条件：按日期范围过滤
            scrape_logger.info("调用 _filter_by_date 方法")
            original_count = len(final_results)
            final_results = self._filter_by_date(final_results, date_range, custom_date_range)

            # 如果日期过滤后没有任何结果，说明 HTML 中的日期不可靠
            # 回退策略：从 URL 中提取日期作为备选
            if len(final_results) == 0 and original_count > 0:
                scrape_logger.warning(f"HTML 日期提取不可靠，所有文章都被过滤，回退到 URL 日期策略")
                for result in final_results:
                    url_date = self._extract_date_from_url(result.url)
                    if url_date:
                        result.published_at = url_date
                        scrape_logger.debug(f"URL 提取日期: {result.url} -> {url_date}")
                # 重新应用日期过滤
                final_results = self._filter_by_date(final_results, date_range, custom_date_range)

            # 如果仍然没有结果（URL 日期也无效），使用 URL 日期对所有文章排序
            if len(final_results) == 0 and original_count > 0:
                scrape_logger.warning(f"使用 URL 日期作为回退方案，按 URL 日期排序")
                for result in final_results:
                    url_date = self._extract_date_from_url(result.url)
                    if url_date:
                        result.published_at = url_date
                # 按 URL 日期排序后返回
                final_results = self._sort_by_published_date(final_results)
                final_results = final_results[:max_articles]
                scrape_logger.info(f"URL 日期回退后选取 {len(final_results)} 篇文章")
        else:
            # 无日期过滤条件：按发布日期排序，取最新的文章
            scrape_logger.info("无日期过滤，按发布日期排序取最新文章")
            final_results = self._sort_by_published_date(final_results)

            # 如果所有文章都没有有效日期，尝试从 URL 提取日期
            valid_date_count = sum(1 for r in final_results if r.published_at)
            if valid_date_count == 0:
                scrape_logger.warning("所有文章 HTML 日期无效，回退到 URL 日期")
                for result in final_results:
                    url_date = self._extract_date_from_url(result.url)
                    if url_date:
                        result.published_at = url_date
                        scrape_logger.debug(f"URL 提取日期: {result.url} -> {url_date}")
                final_results = self._sort_by_published_date(final_results)

            final_results = final_results[:max_articles]  # 限制数量
            scrape_logger.info(f"选取最新 {len(final_results)} 篇文章")

        # 5. 过滤内容过少的文章
        original_count = len(final_results)
        final_results = [
            r for r in final_results
            if r.word_count >= MIN_CONTENT_WORDS or r.status != "success"
        ]
        filtered_count = original_count - len(final_results)
        if filtered_count > 0:
            logger.info(f"过滤了 {filtered_count} 篇内容过少的文章（少于 {MIN_CONTENT_WORDS} 字）")

        # 发送完成事件
        total_articles = len(final_results)
        progress_manager.set_progress(scrape_id, {
            "status": "completed" if not cancelled else "cancelled",
            "stage": 5,
            "stage_name": "已完成" if not cancelled else "已取消",
            "stage_detail": f"成功爬取 {total_articles} 篇文章" if not cancelled else f"爬取已取消，已获取 {total_articles} 篇",
            "current": total_articles,
            "total": total_articles,
        })

        # 记录深度爬取总结
        if cancelled:
            scrape_logger.info(f"爬取已取消 | 总数={len(final_results)}, 成功={success_count}, 已取消={cancelled_count}")
        scrape_logger.log_deep_scrape_result(url, len(final_results), success_count, len(final_results) - success_count)

        logger.info(f"深度爬取完成: {len(final_results)} 篇文章（原始 {original_count} 篇，过滤 {filtered_count} 篇）")
        return list_page_result, final_results


# 全局爬取器实例
_scraper: Optional[WebScraper] = None


def get_scraper() -> WebScraper:
    """获取全局爬取器实例"""
    global _scraper
    if _scraper is None:
        _scraper = WebScraper()
    return _scraper