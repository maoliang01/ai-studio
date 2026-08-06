"""
备用网页爬取器

核心目标：
1. 不依赖 Firecrawl / Crawl4AI，使用 httpx + 内置提取器作为最后一道回退
2. 同时调用多个提取器（Trafilatura / Readability / Density），按"正文质量评分"挑选最优结果
3. 评分维度：
   - 文本长度（饱和上限）
   - 正向信号：中文标点、新闻体关键词
   - 负向信号：栏目串、版权、备案、地址电话、明显导航
4. 选中的结果再做一次"语义尾部裁剪"，剥离页面尾部混入的导航/页脚/版权信息

对外接口：scrape(url, cookies=None, headers=None) -> Dict[str, Any]
返回结构与主 WebScraper 对齐，便于上层无差别使用。
"""

import logging
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx

from app.services.extractor_registry import ExtractorRegistry
from app.services.extractors.base import ExtractedContent

logger = logging.getLogger(__name__)


# ============================================================
# 语义噪声块裁剪
# ============================================================

# 关键截断标记：一旦在正文中发现这些“导航/页脚/版权”串，
# 就把从该位置往后的内容全部丢弃。
NOISE_CUT_MARKERS: List[str] = [
    # 栏目串 / 导航
    r"更多\s*\+\s*科技奖励",
    r"更多\s*\+\s*科技期刊",
    r"更多\s*\+\s*科技专项",
    r"更多\s*\+\s*科研进展",
    # 单独出现的"更多+"（通常是“加载更多”或“阅读更多”按钮）
    # 要求后面不接其他正文字符，避免误伤正文里出现“更多+xxx”这种表达
    r"更多\s*\+(?![一-龥A-Za-z0-9])",
    r"科技奖励\s*科技期刊\s*科技专项",
    r"科技奖励\s*科技专项\s*科技期刊",
    r"中国科学院学部\s*中国科学院院部",
    r"院部\s*院士\s*机构",
    r"机构\s*院士\s*院部",
    r"^(首页|走进科学院|信息公开|科技人才|院士|出版物|新闻动态|图片世界|视频世界)\s*[|·\-\s]",
    # 版权 / 备案
    r"©?\s*1996\s*[-—–]\s*\d{0,4}\s*中国科学院\s*版权所有",
    r"中国科学院\s*版权所有",
    r"京ICP备\s*\d+\s*号",
    r"京公网安备\s*\d+\s*号",
    r"网站标识码\s*[：:]\s*\S+",
    # 联系信息
    r"地址[：:]\s*北京市西城区三里河路\s*52\s*号",
    r"邮编[：:]\s*100864",
    r"电话[：:]\s*86[\s\-]*\d{2,3}[\s\-]*\d{6,8}",
    r"邮件[：:]\s*\\?cas\\?@\\?cas\\?\\.\\?[a-z.]+",
    r"传真[：:]\s*86[\s\-]*\d{2,3}[\s\-]*\d{6,8}",
    # 站内友情链接
    r"友情链接[：:]",
    r"相关链接[：:]",
    r"主办单位[：:]",
    # 分享/工具栏残留
    r"更多分享",
    r"打印\s*页面",
    r"分享到\s*[^\s]+",
    r"浏览量[：:]\s*\d+",
]

# 编译为单条复合正则，匹配任一即可触发截断
_NOISE_CUT_RE = re.compile("|".join(f"(?:{p})" for p in NOISE_CUT_MARKERS), re.IGNORECASE)


def strip_semantic_noise_blocks(content: str) -> str:
    """
    语义尾部裁剪：定位文本中“开始变像导航/页脚/版权”的位置，从该处截断。

    设计：
    - 首先规范化空白（\\s+ → 单空格）用于模式匹配
    - 顺序扫描所有 NOISE_CUT_MARKERS，取最早出现的位置作为截断点
    - 截断后做尾部清理（空白 + 标点），避免残留
    - 最后尽量把空白还原为原文的换行：按"原文行累计字符数"做近似还原
    - 如果原始内容没有换行，直接返回规范化后的裁剪结果
    - 找不到任何标记时原样返回
    """
    if not content:
        return content

    # 保留原始换行结构以减少破坏，先做归一化扫描
    normalized = re.sub(r"\s+", " ", content).strip()
    if not normalized:
        return content

    cut_pos = len(normalized)
    match = _NOISE_CUT_RE.search(normalized)
    if match:
        cut_pos = match.start()

    # 把 cut_pos 之前的内容做尾部清理
    cleaned_norm = normalized[:cut_pos].rstrip(" \t\r\n,;，；。:：")
    if not cleaned_norm:
        # 极端情况：整篇全是导航；至少返回原文的前一段，避免空结果
        return content[: min(len(content), 200)]

    # 尝试把"按行拆分"近似还原：用原文按 splitlines() 后的行做累计
    # 累计的是 normalized 形式（单空格）下的字符数，超过 cleaned_norm 长度就停
    original_lines = content.splitlines()
    if len(original_lines) <= 1:
        # 单行内容：直接返回 normalized（行内换行已被压平）
        return cleaned_norm

    # 用未 rstrip 的长度做上界（包含末尾的 "。"）
    upper_bound = len(normalized[:cut_pos])

    head_lines: List[str] = []
    consumed = 0
    for line in original_lines:
        stripped = line.strip()
        if not stripped:
            # 空行：在已加入首段后才保留，避免前导空行
            if head_lines:
                head_lines.append(line)
            continue
        # 这一行能否完整放入？
        if consumed + len(stripped) + 1 > upper_bound:
            # 整行放不下了，看部分能否放
            remaining = upper_bound - consumed
            if remaining > 0 and len(stripped) > remaining:
                # 截取部分内容
                head_lines.append(stripped[:remaining])
            elif remaining >= len(stripped):
                # 刚好能放下（理论上不会进这里，但兜底）
                head_lines.append(line)
            break
        head_lines.append(line)
        consumed += len(stripped) + 1

    if not head_lines:
        return cleaned_norm

    return "\n".join(head_lines).strip()


# ============================================================
# 提取质量评分
# ============================================================

# 中文正文里典型的句末/句中标点，密度高通常是真正的新闻/文章
_POSITIVE_PUNCTUATION = re.compile(r"[。！？；：]")

# 新闻/学术类正文里常出现的高质量关键词
_POSITIVE_KEYWORDS = re.compile(
    r"(成立|贯彻落实|建院|发展|研究|任务|贡献|推动|促进|实施|开展|"
    r"习近平|总书记|指出|强调|要求|会议|讲话|工作|"
    r"日前|近日|近日来|日前来|报道|获悉|"
    r"重要|关键|目标|计划|方案|意见|精神|部署|举措)"
)

# 明显的导航/页脚/版权/联系方式/栏目串
_NEGATIVE_PATTERNS = [
    re.compile(r"更多\s*\+"),
    re.compile(r"(版权所有|版权©|©copyright)", re.IGNORECASE),
    re.compile(r"(京ICP备|京公网安备|网站标识码)"),
    re.compile(r"(地址[：:]|邮编[：:]|电话[：:]|传真[：:]|邮箱[：:]|邮件[：:])"),
    re.compile(r"(科技奖励|科技期刊|科技专项|科研进展|科技人才|科技合作)"),
    re.compile(r"(中国科学院学部|中国科学院院部|院部|学部|机构|院士)"),
    re.compile(r"(首页|走进科学院|信息公开|新闻动态|图片世界|视频世界|出版物)\s*[|·\-]"),
    re.compile(r"友情链接[：:]"),
    re.compile(r"分享到|打印\s*页面|更多分享"),
    re.compile(r"^\s*(home|about|contact|login|register)\s*$", re.IGNORECASE),
    re.compile(r"^\s*\[.+?\]\([^)]+\)\s*$"),  # 单个链接行
]

_NAV_LIKE_TAIL = re.compile(
    r"(\bhome\b|\babout\b|\bcontact\b|\b登录\b|\b注册\b|\b首页\b|"
    r"\bEN\b|\bEnglish\b|\bEnglish\s*Version\b|返回顶部|"
    r"网站地图|站点地图|sitemap|"
    r"主办单位|承办单位|承办[：:]|主办[：:])",
    re.IGNORECASE,
)


def _score_extracted_text(text: str, title: str = "") -> float:
    """
    评估一段被提取的“正文”质量。

    评分规则：
    - 长度：取前 2000 字符计算，长度越长越好（饱和）
    - 正向奖励：中文标点密度、新闻体关键词命中
    - 负向惩罚：栏目串、版权、备案、地址电话、英文导航词
    - 标题一致性奖励：标题中的关键词出现在正文，提示是相关文章
    """
    if not text:
        return float("-inf")

    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return float("-inf")

    # 长度项：min(2000)/20，封顶 100
    length_score = min(len(normalized), 2000) / 20.0

    # 正向项
    positive_score = 0.0
    positive_score += len(_POSITIVE_PUNCTUATION.findall(normalized)) * 1.0
    positive_score += len(_POSITIVE_KEYWORDS.findall(normalized)) * 1.5

    # 负向项
    negative_score = 0.0
    for pat in _NEGATIVE_PATTERNS:
        hits = pat.findall(normalized)
        negative_score += len(hits) * 4.0

    # 导航尾部：文本最后 200 字符若密集出现导航词，再惩罚
    tail_window = normalized[-200:] if len(normalized) > 200 else normalized
    negative_score += len(_NAV_LIKE_TAIL.findall(tail_window)) * 2.0

    # 标题一致性奖励
    title_bonus = 0.0
    if title:
        # 取标题中较长的 2~6 字中文片段，看是否出现在正文
        candidates = re.findall(r"[\u4e00-\u9fa5]{2,8}", title)
        hit = 0
        for c in candidates:
            if c in normalized:
                hit += 1
        if candidates:
            title_bonus = (hit / len(candidates)) * 8.0

    return length_score + positive_score + title_bonus - negative_score


def _deduplicate_duplicate_blocks(text: str) -> str:
    """
    结构去重：检测并删除内容中的"扁平副本块"。

    背景：
    cas.cn 等使用 TRS_UEDITOR 的站点，会在 HTML 中同时输出两套正文：
      1. ``<div class="xl_content">`` 下用 ``<p>`` 标签格式化的多段版本
      2. ``<p id="_content">`` 一整段扁平拼接的版本（用于打印/无障碍/SEO）
    Mozilla Readability 把两个容器都识别为"主内容"并全部纳入 ``summary()``，
    导致 final text 出现完整的二次重复。

    算法：
    1. 按 ``\\n+`` 切块（与 readability/clean_content 输出格式一致：单换行分段）
    2. 规范化每个块：去除所有空白字符
    3. 检查 1（结构性副本）：
       遍历每个块，若其规范化文本等于"其余所有块拼接"的规范化文本，
       则认为它是扁平副本，删除。
    4. 检查 2（完全重复）：若两个块规范化后完全相同，删除后者。
    5. 没有重复时原样返回，避免误伤。

    Args:
        text: 任意正文文本

    Returns:
        去重后的文本；若无重复或无法判定则原样返回
    """
    if not text:
        return text

    # 按换行切块（与 readability/clean_content 输出格式一致：单换行分段）
    # 过滤空块和仅含空白的块
    blocks = [b for b in re.split(r"\n+", text) if b.strip()]
    if len(blocks) < 2:
        return text

    # 规范化：去除所有空白，便于跨块内容比对
    normalized = [re.sub(r"\s+", "", b) for b in blocks]

    # 过滤掉规范化后为空的块（极端情况）
    valid_pairs = [(i, ni) for i, ni in enumerate(normalized) if ni]
    if len(valid_pairs) < 2:
        return text

    to_remove: set = set()

    # 检查 1：是否存在"某个块 = 其余所有块拼接"的扁平副本
    # 要求：至少 3 个块。少于 3 个块时，"其余"只有一个块，若与当前块相等
    # 属于"完全相同"场景，由 Check 2 处理更合适（保留前者）。
    if len(valid_pairs) >= 3:
        for i, ni in valid_pairs:
            if i in to_remove:
                continue
            others_concat = "".join(
                nj for j, nj in valid_pairs if j != i and j not in to_remove
            )
            if ni == others_concat and len(ni) >= 50:
                # 该块是其余所有块的扁平拼接副本
                to_remove.add(i)

    # 检查 2：两个块完全相同 → 删除后者（保留靠前的）
    for i in range(len(blocks)):
        if i in to_remove or not normalized[i]:
            continue
        for j in range(i + 1, len(blocks)):
            if j in to_remove or not normalized[j]:
                continue
            if normalized[i] == normalized[j] and len(normalized[i]) >= 50:
                to_remove.add(j)

    # Check 3：跨块公共子串（处理 Crawl4AI 风格扁平副本）
    # 必须放在 early return 之前，因为 Check 1/2 都可能不触发
    to_remove = _remove_substring_duplicate(blocks, normalized, to_remove)

    if not to_remove:
        return text

    kept = [b for i, b in enumerate(blocks) if i not in to_remove]
    return "\n".join(kept)


def _remove_substring_duplicate(blocks: list, normalized: list, to_remove: set) -> set:
    """
    Check 3：用 SequenceMatcher 找跨块的"长公共子串"。

    处理 Crawl4AI 等场景的"扁平副本"模式：
    原文:  [p1, p2, p3, flat_dup]   其中 flat_dup = p1 + p2 + p3 (无 \n)
    按 \n+ 切后: 块级 dedup 检测不出（flat_dup 是单块，不等任何其他块）
    但归一化后 flat_dup 包含 p1、p2、p3 的子串 → 应删除 flat_dup

    规则：任一 block (归一化后) 完全包含在另一个 block (归一化后) 里，
    且长度都 >= 50，则删除那个被包含的（更短的那个）。

    Returns:
        更新后的 to_remove 集合
    """
    new_to_remove = set(to_remove)
    n = len(blocks)
    for i in range(n):
        if i in new_to_remove or not normalized[i] or len(normalized[i]) < 50:
            continue
        for j in range(n):
            if i == j or j in new_to_remove or not normalized[j] or len(normalized[j]) < 50:
                continue
            if normalized[i] in normalized[j]:
                # i 是 j 的子串 → 删 j（j 是包含重复内容的超集）
                # 但要选"更短且完整"那个删。这里 i 比 j 短，删 j 保留 i
                new_to_remove.add(j)
                break
            if normalized[j] in normalized[i]:
                # j 是 i 的子串 → 删 j
                new_to_remove.add(j)
                # 不要 break，因为可能有多个 j 都被 i 包含
    return new_to_remove


def _select_best_extraction(
    candidates: List[Dict[str, Any]],
    title: str = "",
) -> Dict[str, Any]:
    """
    从多个提取器的结果中选出最佳的一个。

    candidates: [{"extractor": "trafilatura", "text": "...", "html": "..."}, ...]
    """
    best: Optional[Dict[str, Any]] = None
    best_score = float("-inf")

    for c in candidates:
        text = (c.get("text") or "").strip()
        if not text:
            continue
        score = _score_extracted_text(text, title=title)
        logger.info(
            f"  - 提取器 {c.get('extractor')}: len={len(text)} score={score:.2f}"
        )
        if score > best_score:
            best_score = score
            best = c

    if best is None:
        # 全部为空时回退到第一个非空
        for c in candidates:
            if c.get("text") or c.get("html"):
                return c
        return candidates[0] if candidates else {}

    return best


# ============================================================
# AlternateScraper
# ============================================================

class AlternateScraper:
    """
    备用爬取器：httpx + 多个正文提取器 + 质量评分。

    适用于：
    - Firecrawl 不可用（API Key 缺失 / 离线）
    - Crawl4AI 不可用（依赖未装 / 浏览器不可用）
    - 站点对 JS 渲染依赖低，可纯 HTTP 抓取 + 静态正文提取
    """

    DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.registry = ExtractorRegistry()
        self.headers = dict(self.DEFAULT_HEADERS)

    def _parse_cookies(self, cookies: Optional[str]) -> Dict[str, str]:
        if not cookies:
            return {}
        result: Dict[str, str] = {}
        # 接受 "k1=v1; k2=v2" 形式
        for part in re.split(r"[;\n]", cookies):
            part = part.strip()
            if not part or "=" not in part:
                continue
            k, v = part.split("=", 1)
            result[k.strip()] = v.strip()
        return result

    def _clean_html_tags(self, html: str) -> str:
        """简单去掉 HTML 标签，避免提取结果混入原始 HTML。"""
        if not html:
            return html
        text = re.sub(r"<[^>]+>", "", html)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    async def scrape(
        self,
        url: str,
        cookies: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        主入口：HTTP 抓取 + 多提取器对比 + 评分选最优。

        Returns:
            {
                "success": bool,
                "content": str,        # 最终正文（已语义裁剪）
                "markdown": str,       # markdown（如果没有则是 content）
                "title": str,
                "html": str,           # 原始 HTML
                "links": List[str],
                "metadata": dict,
                "extractor": str,      # 命中的提取器名
                "extractor_score": float,
                "raw_candidates": List[dict],  # 所有候选评分快照
            }
        """
        result: Dict[str, Any] = {
            "success": False,
            "content": "",
            "markdown": "",
            "title": "",
            "html": "",
            "links": [],
            "metadata": {},
            "extractor": "",
            "extractor_score": float("-inf"),
            "raw_candidates": [],
            "error": "",
        }

        try:
            request_headers = dict(self.headers)
            if headers:
                request_headers.update(headers)

            cookie_dict = self._parse_cookies(cookies)

            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                verify=False,
            ) as client:
                response = await client.get(
                    url, headers=request_headers, cookies=cookie_dict
                )
                response.raise_for_status()
                html = response.text
                result["html"] = html
                result["success"] = True
                result["metadata"]["status_code"] = response.status_code
                result["metadata"]["final_url"] = str(response.url)
                # 尝试从 HTML 中提取发布日期
                published = _extract_publish_date_from_html(html)
                if published:
                    result["metadata"]["published_at"] = published

            # 提取阶段：每个 extractor 一次
            candidates: List[Dict[str, Any]] = []
            for extractor in self.registry.get_all_extractors():
                try:
                    extracted: ExtractedContent = extractor.extract(html, url=url)
                except Exception as e:  # 单个提取器失败不影响整体
                    logger.warning(f"提取器 {extractor.name} 异常: {e}")
                    continue

                text = (extracted.text or "").strip() or self._clean_html_tags(
                    extracted.content or ""
                )
                if not text:
                    continue
                candidates.append(
                    {
                        "extractor": extractor.name,
                        "text": text,
                        "html": extracted.content or "",
                        "title": extracted.title or "",
                    }
                )

            if not candidates:
                result["error"] = "所有提取器均未返回内容"
                return result

            # 用“第一份”候选的标题作为通用标题，避免漏取
            fallback_title = ""
            for c in candidates:
                if c.get("title"):
                    fallback_title = c["title"]
                    break

            best = _select_best_extraction(candidates, title=fallback_title)
            raw_text = (best.get("text") or "").strip()
            best_title = best.get("title") or fallback_title or ""

            # 二次净化：strip_semantic_noise_blocks
            cleaned_text = strip_semantic_noise_blocks(raw_text)

            # 三次净化：结构去重（cas.cn TRS_UEDITOR 等站点会在 HTML 中输出
            # 2 份正文：格式化 + 扁平 <p id="_content">，Readability 把两份
            # 都纳入后会形成完整重复。必须在送分/送 LLM 之前消除。）
            cleaned_text = _deduplicate_duplicate_blocks(cleaned_text)

            result["content"] = cleaned_text
            result["markdown"] = cleaned_text
            result["title"] = best_title
            result["extractor"] = best.get("extractor", "")
            result["extractor_score"] = _score_extracted_text(raw_text, title=best_title)
            result["raw_candidates"] = [
                {
                    "extractor": c.get("extractor"),
                    "length": len(c.get("text", "")),
                    "score": _score_extracted_text(
                        c.get("text", ""), title=best_title
                    ),
                }
                for c in candidates
            ]
            result["links"] = self._extract_links(html, url)

        except httpx.HTTPStatusError as e:
            result["error"] = f"HTTP {e.response.status_code}: {e}"
            logger.error(f"备用爬取 HTTP 失败: {url} - {e}")
        except httpx.RequestError as e:
            result["error"] = f"请求失败: {e}"
            logger.error(f"备用爬取请求失败: {url} - {e}")
        except Exception as e:
            result["error"] = f"未知错误: {e}"
            logger.exception(f"备用爬取异常: {url}")

        return result

    def _extract_links(self, html: str, base_url: str) -> List[str]:
        """从 HTML 中抽取有效链接（绝对 URL）。"""
        if not html:
            return []
        from bs4 import BeautifulSoup  # 局部导入，避免对 import 顺序产生硬依赖
        from urllib.parse import urljoin

        try:
            soup = BeautifulSoup(html, "lxml")
        except Exception:
            soup = BeautifulSoup(html, "html.parser")

        links: List[str] = []
        seen = set()
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript:"):
                continue
            absolute = urljoin(base_url, href)
            if absolute in seen:
                continue
            seen.add(absolute)
            links.append(absolute)
        return links


# ============================================================
# 单例
# ============================================================

_alternate_scraper: Optional[AlternateScraper] = None


def get_alternate_scraper() -> AlternateScraper:
    global _alternate_scraper
    if _alternate_scraper is None:
        _alternate_scraper = AlternateScraper()
    return _alternate_scraper


def reset_alternate_scraper() -> None:
    global _alternate_scraper
    _alternate_scraper = None
