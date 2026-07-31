# -*- coding: utf-8 -*-
"""
微信公众号爬虫封装

基于 Playwright 实现微信公众号文章爬取
"""

import json
import asyncio
import logging
import re
import httpx
from datetime import datetime, date
from zoneinfo import ZoneInfo
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from bs4 import BeautifulSoup, NavigableString, Tag

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright
)

from app.services.wechat.cookie_manager import CookieManager

logger = logging.getLogger(__name__)


@dataclass
class WechatArticle:
    """微信公众号文章数据结构"""
    url: str
    title: str
    content: str
    author: str = ""
    publish_time: str = ""
    source_name: str = ""
    summary: str = ""
    tags: List[str] = field(default_factory=list)
    html: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "author": self.author,
            "publish_time": self.publish_time,
            "source_name": self.source_name,
            "summary": self.summary,
            "tags": self.tags,
            "html": self.html,
        }


class WechatCrawler:
    """微信公众号爬虫"""

    def __init__(self, cookie_manager: CookieManager):
        self.cookie_manager = cookie_manager
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self.errors: Dict[str, str] = {}
        self.discovery_info: Dict[str, Any] = {}

    async def start(self) -> None:
        """启动浏览器"""
        self._playwright = await async_playwright().start()
        try:
            # Windows 上优先复用系统 Chrome。部分安全策略会阻止 Playwright
            # 内置 Chromium 联网，但允许已安装且受信任的 Chrome 访问。
            self._browser = await self._playwright.chromium.launch(
                channel="chrome",
                headless=True,
            )
            logger.info("系统 Chrome 启动成功")
        except Exception as exc:
            logger.warning("系统 Chrome 启动失败，回退到 Playwright Chromium: %s", exc)
            self._browser = await self._playwright.chromium.launch(headless=True)
            logger.info("Playwright Chromium 启动成功")

    async def stop(self) -> None:
        """停止浏览器"""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("浏览器已停止")

    async def _ensure_context(self) -> BrowserContext:
        """确保浏览器上下文已创建并加载 Cookie"""
        if self._context is None:
            # 创建浏览器上下文
            self._context = await self._browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # 尝试获取激活的 Cookie
            try:
                cookie = await self.cookie_manager.get_active_cookie()
                if cookie:
                    # 加载 Cookie
                    raw_cookies = json.loads(cookie.cookie_data)
                    if isinstance(raw_cookies, dict):
                        raw_cookies = raw_cookies.get("cookies", [])
                    cookies = []
                    allowed_fields = {"name", "value", "url", "domain", "path", "expires", "httpOnly", "secure", "sameSite"}
                    for raw_cookie in raw_cookies:
                        normalized = {key: value for key, value in raw_cookie.items() if key in allowed_fields}
                        same_site = normalized.pop("sameSite", None)
                        if isinstance(same_site, str):
                            same_site_map = {
                                "strict": "Strict",
                                "lax": "Lax",
                                "none": "None",
                                "no_restriction": "None",
                            }
                            mapped = same_site_map.get(same_site.lower())
                            if mapped:
                                normalized["sameSite"] = mapped
                        # Cookie-Editor 可能导出 null、unspecified 等 Playwright
                        # 不接受的值。无法明确映射时直接省略，让浏览器使用默认值。
                        cookies.append(normalized)
                    await self._context.add_cookies(cookies)

                    # 更新最后使用时间
                    await self.cookie_manager.update_last_used(cookie.id)

                    logger.info(f"已加载 Cookie: {cookie.name}")
                else:
                    logger.warning("没有可用的 Cookie，将尝试无 Cookie 模式爬取")
            except Exception as e:
                logger.warning(f"获取 Cookie 失败: {e}，将尝试无 Cookie 模式爬取")

        return self._context

    async def fetch_article(self, url: str) -> Optional[WechatArticle]:
        """
        爬取单篇文章

        Args:
            url: 文章 URL

        Returns:
            WechatArticle 对象，如果失败则返回 None
        """
        self.errors.pop(url, None)
        context = await self._ensure_context()
        page: Optional[Page] = None

        try:
            # 创建新页面
            page = await context.new_page()

            # 访问文章
            logger.info(f"正在爬取文章: {url}")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # 检查是否有错误消息
            error_msg = await page.query_selector(".weui-msg__title")
            if error_msg:
                error_text = await error_msg.text_content()
                if error_text and ("错误" in error_text or "已迁移" in error_text or "已过期" in error_text):
                    logger.warning(f"文章不可用: {error_text}")
                    self.errors[url] = error_text.strip()
                    return None

            # 等待文章加载
            try:
                await page.wait_for_selector("#activity-name", timeout=10000)
            except Exception:
                # 尝试其他选择器
                try:
                    await page.wait_for_selector(".rich_media_title", timeout=5000)
                except Exception:
                    logger.warning(f"文章页面加载超时: {url}")
                    self.errors[url] = "文章页面加载超时，未找到标题区域"
                    return None

            # 提取文章信息
            title = await self._extract_title(page)
            content = await self._extract_content(page)
            author = await self._extract_author(page)
            publish_time = await self._extract_publish_time(page)
            source_name = await self._extract_source_name(page)
            html = await page.content()

            if not title or not content:
                logger.warning(f"文章内容提取失败: {url}")
                self.errors[url] = "页面已打开，但未提取到标题或正文"
                return None

            article = WechatArticle(
                url=url,
                title=title,
                content=content,
                author=author,
                publish_time=publish_time,
                source_name=source_name,
                html=html
            )

            logger.info(f"文章爬取成功: {title}")
            return article

        except Exception as e:
            logger.error(f"爬取文章失败: {url}, 错误: {e}")
            self.errors[url] = str(e) or repr(e) or "未知爬取错误"
            return None
        finally:
            if page:
                await page.close()

    async def _extract_title(self, page: Page) -> str:
        """提取文章标题"""
        try:
            # 尝试多个选择器
            selectors = ["#activity-name", ".rich_media_title", "h1"]
            for selector in selectors:
                title_element = await page.query_selector(selector)
                if title_element:
                    text = (await title_element.inner_text()).strip()
                    if text:
                        return text
        except Exception as e:
            logger.debug(f"提取标题失败: {e}")
        return ""

    async def extract_account_profile(self, url: str) -> Dict[str, str]:
        """从一篇公开公众号文章中提取发布公众号档案信息。"""
        parsed = urlparse(url.strip())
        if parsed.scheme not in {"http", "https"} or parsed.hostname != "mp.weixin.qq.com" or not parsed.path.startswith("/s"):
            raise ValueError("请输入有效的 mp.weixin.qq.com/s/... 公众号文章链接")

        context = await self._ensure_context()
        page = await context.new_page()
        try:
            await page.goto(url.strip(), wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(800)

            account_name = await self._extract_source_name(page)
            title = ""
            title_element = await page.query_selector("#activity-name")
            if title_element:
                title = (await title_element.inner_text()).strip()
            publish_time = await self._extract_publish_time(page)
            html = await page.content()

            if not account_name:
                for pattern in (
                    r"var\s+nickname\s*=\s*htmlDecode\([\"'](.*?)[\"']\)",
                    r"nickname\s*:\s*[\"'](.*?)[\"']",
                ):
                    match = re.search(pattern, html)
                    if match:
                        account_name = BeautifulSoup(match.group(1), "html.parser").get_text().strip()
                        break
            if not account_name:
                raise RuntimeError("未能从文章页面识别公众号名称，请确认链接可正常打开且不是临时预览链接")

            wechat_id = ""
            for pattern in (
                r"var\s+user_name\s*=\s*[\"']([^\"']+)[\"']",
                r"user_name\s*:\s*[\"']([^\"']+)[\"']",
            ):
                match = re.search(pattern, html)
                if match and match.group(1) not in {"", "null", "undefined"}:
                    wechat_id = match.group(1).strip()
                    break

            return {
                "name": account_name,
                "wechat_id": wechat_id,
                "sample_article_url": page.url,
                "sample_article_title": title,
                "sample_article_published_at": publish_time,
            }
        finally:
            await page.close()

    async def _extract_content(self, page: Page) -> str:
        """提取文章正文并转换为与网页爬取一致的 Markdown。"""
        try:
            # 尝试多个选择器
            selectors = ["#js_content", ".rich_media_content", "article"]
            for selector in selectors:
                content_element = await page.query_selector(selector)
                if content_element:
                    content_html = await content_element.inner_html()
                    markdown = self._html_to_markdown(content_html)
                    if markdown:
                        return markdown
        except Exception as e:
            logger.debug(f"提取内容失败: {e}")
        return ""

    @staticmethod
    def _html_to_markdown(content_html: str) -> str:
        """将微信正文 HTML 转为结构化 Markdown，保留标题、列表、链接和图片。"""
        soup = BeautifulSoup(content_html, "html.parser")
        for node in soup(["script", "style", "noscript", "iframe"]):
            node.decompose()

        def render(node: Any, list_depth: int = 0) -> str:
            if isinstance(node, NavigableString):
                return re.sub(r"[ \t\r\f\v]+", " ", str(node))
            if not isinstance(node, Tag):
                return ""
            name = node.name.lower()
            children = "".join(render(child, list_depth) for child in node.children).strip()
            if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
                return f"\n{'#' * int(name[1])} {children}\n"
            if name == "p":
                return f"\n{children}\n" if children else ""
            if name == "br":
                return "  \n"
            if name in {"strong", "b"}:
                return f"**{children}**" if children else ""
            if name in {"em", "i"}:
                return f"*{children}*" if children else ""
            if name == "blockquote":
                return "\n" + "\n".join(f"> {line}" for line in children.splitlines() if line.strip()) + "\n"
            if name == "a":
                href = node.get("href", "")
                return f"[{children or href}]({href})" if href else children
            if name == "img":
                src = node.get("data-src") or node.get("src") or ""
                alt = node.get("alt") or node.get("title") or "图片"
                return f"\n![{alt}]({src})\n" if src else ""
            if name in {"ul", "ol"}:
                return f"\n{children}\n"
            if name == "li":
                prefix = "1." if node.parent and node.parent.name == "ol" else "-"
                return f"\n{'  ' * list_depth}{prefix} {children}"
            if name in {"section", "div", "article"}:
                return f"\n{children}\n"
            return children

        markdown = render(soup)
        markdown = re.sub(r"\n[ \t]+\n", "\n\n", markdown)
        markdown = re.sub(r"\n{3,}", "\n\n", markdown)
        return markdown.strip()

    async def discover_account_articles(
        self,
        account_name: str,
        wechat_id: str = "",
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        max_articles: int = 50,
        known_fakeid: str = "",
    ) -> List[Dict[str, Any]]:
        """通过公众号后台接口发现指定公众号在日期范围内发布的文章。"""
        active_cookie = await self.cookie_manager.get_active_cookie()
        if not active_cookie:
            raise RuntimeError("没有可用的公众号后台 Cookie")
        raw_cookies = json.loads(active_cookie.cookie_data)
        if isinstance(raw_cookies, dict):
            raw_cookies = raw_cookies.get("cookies", [])
        cookie_values = {
            str(item.get("name")): str(item.get("value", ""))
            for item in raw_cookies
            if isinstance(item, dict) and item.get("name")
        }
        client = httpx.AsyncClient(
            cookies=cookie_values,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9",
            },
            follow_redirects=True,
            timeout=30.0,
        )
        try:
            # 使用项目 HTTP 客户端避开 Windows 对 Playwright/Chrome 网络栈的
            # ERR_NETWORK_ACCESS_DENIED / EACCES 限制。
            homepage_response = await client.get("https://mp.weixin.qq.com/")
            token = parse_qs(urlparse(str(homepage_response.url)).query).get("token", [""])[0]
            if not token:
                raise RuntimeError(
                    "公众号后台 Cookie 未登录、已失效或未进入管理后台，无法获取 token；"
                    "请在浏览器登录 mp.weixin.qq.com 后，从 URL 带 token= 的后台页面重新导出 Cookie"
                )

            query = wechat_id or account_name
            if known_fakeid:
                search_data = {"list": [{
                    "nickname": account_name,
                    "alias": wechat_id,
                    "fakeid": known_fakeid,
                }]}
            else:
                search_params = urlencode({
                    "action": "search_biz", "begin": 0, "count": 10,
                    "query": query, "token": token, "lang": "zh_CN", "f": "json", "ajax": 1,
                })
                search_response = await client.get(f"https://mp.weixin.qq.com/cgi-bin/searchbiz?{search_params}")
                search_data = search_response.json()
            candidates = search_data.get("list") or []
            if not candidates:
                raise RuntimeError(f"未找到公众号“{query}”，请检查名称/ID及后台 Cookie 权限")
            normalized_name = account_name.strip().casefold()
            normalized_wechat_id = wechat_id.strip().casefold()
            selected = next(
                (
                    item for item in candidates
                    if str(item.get("nickname", "")).strip().casefold() == normalized_name
                    or (
                        normalized_wechat_id
                        and str(item.get("alias", "")).strip().casefold() == normalized_wechat_id
                    )
                ),
                None,
            )
            if not selected:
                candidate_names = "、".join(
                    str(item.get("nickname", "")).strip()
                    for item in candidates[:5]
                    if item.get("nickname")
                )
                raise RuntimeError(
                    f"未能精确匹配公众号“{account_name}”。后台搜索候选：{candidate_names or '无'}。"
                    "请在公众号档案中补充微信号，避免同名或近似名称误匹配。"
                )
            fakeid = selected.get("fakeid")
            if not fakeid:
                raise RuntimeError("公众号搜索结果缺少 fakeid")

            discovered: List[Dict[str, Any]] = []
            self.discovery_info = {
                "requested_name": account_name,
                "matched_name": selected.get("nickname", ""),
                "matched_alias": selected.get("alias", ""),
                "fakeid": fakeid,
                "latest_date": "",
                "oldest_date": "",
            }
            begin = 0
            page_size = 10
            while len(discovered) < max_articles and begin < 500:
                params = urlencode({
                    "action": "list_ex", "begin": begin, "count": page_size,
                    "fakeid": fakeid, "type": 9, "query": "", "token": token,
                    "lang": "zh_CN", "f": "json", "ajax": 1,
                })
                response = await client.get(f"https://mp.weixin.qq.com/cgi-bin/appmsg?{params}")
                payload = response.json()
                items = payload.get("app_msg_list") or []
                self.discovery_info.update({
                    "response_ret": payload.get("ret", payload.get("base_resp", {}).get("ret")),
                    "response_error": payload.get("errmsg", payload.get("base_resp", {}).get("err_msg", "")),
                    "available_count": payload.get("app_msg_cnt", payload.get("total_count")),
                })
                if not items:
                    break
                page_dates: List[date] = []
                for item in items:
                    # create_time 是首次发布时间；update_time 可能是后续编辑时间，
                    # 不能优先用于发布日期过滤。
                    timestamp = item.get("create_time") or item.get("update_time")
                    published = self._timestamp_to_date(timestamp)
                    if published:
                        page_dates.append(published)
                        current_latest = self.discovery_info.get("latest_date")
                        current_oldest = self.discovery_info.get("oldest_date")
                        if not current_latest or published.isoformat() > current_latest:
                            self.discovery_info["latest_date"] = published.isoformat()
                        if not current_oldest or published.isoformat() < current_oldest:
                            self.discovery_info["oldest_date"] = published.isoformat()
                    if published and start_date and published < start_date:
                        continue
                    if published and end_date and published > end_date:
                        continue
                    link = item.get("link")
                    if link:
                        discovered.append({
                            "url": link,
                            "title": item.get("title", ""),
                            "author": item.get("author_name", ""),
                            "summary": item.get("digest", ""),
                            "published_at": published.isoformat() if published else "",
                        })
                        if len(discovered) >= max_articles:
                            break
                # 后台列表通常按时间倒序，但同一页可能混有更新/多图文记录。
                # 只有整页有日期的记录都早于开始日期时，才能安全停止分页。
                whole_page_before_start = bool(
                    start_date and page_dates and all(item_date < start_date for item_date in page_dates)
                )
                if whole_page_before_start or len(items) < page_size:
                    break
                begin += page_size
                await asyncio.sleep(2)
            return discovered
        finally:
            await client.aclose()

    @staticmethod
    def _timestamp_to_date(value: Any) -> Optional[date]:
        """将公众号接口的秒/毫秒 Unix 时间戳转换为北京时间日期。"""
        if value in (None, ""):
            return None
        try:
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=ZoneInfo("Asia/Shanghai")).date()
        except (TypeError, ValueError, OSError, OverflowError):
            return None

    async def _extract_author(self, page: Page) -> str:
        """提取文章作者"""
        try:
            author_element = await page.query_selector("#js_name")
            if author_element:
                return (await author_element.inner_text()).strip()
        except Exception as e:
            logger.debug(f"提取作者失败: {e}")
        return ""

    async def _extract_publish_time(self, page: Page) -> str:
        """提取发布时间"""
        try:
            time_element = await page.query_selector("#publish_time")
            if time_element:
                return (await time_element.inner_text()).strip()
        except Exception as e:
            logger.debug(f"提取发布时间失败: {e}")
        return ""

    async def _extract_source_name(self, page: Page) -> str:
        """提取来源名称"""
        try:
            source_element = await page.query_selector("#js_name")
            if source_element:
                return (await source_element.inner_text()).strip()
        except Exception as e:
            logger.debug(f"提取来源失败: {e}")
        return ""

    async def fetch_articles_batch(
        self,
        urls: List[str],
        delay: float = 1.0
    ) -> List[WechatArticle]:
        """
        批量爬取文章

        Args:
            urls: 文章 URL 列表
            delay: 每篇文章之间的延迟（秒）

        Returns:
            成功爬取的文章列表
        """
        import asyncio
        articles = []

        for url in urls:
            try:
                article = await self.fetch_article(url)
                if article:
                    articles.append(article)
                # 添加延迟避免被封
                await asyncio.sleep(delay)
            except Exception as e:
                logger.error(f"批量爬取失败: {url}, 错误: {e}")

        return articles

    async def search_articles(
        self,
        keyword: str,
        max_results: int = 10
    ) -> List[str]:
        """
        搜索公众号文章

        Args:
            keyword: 搜索关键词
            max_results: 最大结果数

        Returns:
            文章 URL 列表
        """
        # TODO: 实现微信公众号文章搜索
        # 可以通过搜狗微信搜索或微信公众号后台搜索
        logger.warning("搜索功能尚未实现")
        return []
