"""
页签识别分析服务
使用 AI 自动分析网页的导航菜单和内容区 Tab 结构
"""

import time
import json
import re
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from urllib.parse import urljoin, urlparse
from datetime import datetime

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig

from app.core.llm import llm_service
from app.core.config import get_llm_config

logger = logging.getLogger(__name__)


# LLM 系统提示词
SYSTEM_PROMPT = """你是一个专业的网页结构分析专家。任务是从给定的HTML结构中识别网站的导航菜单和内容区Tab，组织成JSON树形结构。

## 识别要求

### 1. 导航菜单识别
- 识别 <nav> 和 <header> 内的多级菜单结构
- 菜单层级：顶级导航 -> 二级下拉/侧边栏 -> 更多子分类
- 排除：版权信息、联系方式、登录入口、搜索框、社交媒体链接等非分类链接
- URL 为空或 "#" 的是分隔符，不是有效分类

### 2. 内容区Tab识别
- 识别页面主内容区的 Tab 切换组件（如"最新"、"最热"、"推荐"）
- Tab 通常在同一URL下通过参数切换（如 ?tab=latest）
- 只识别有实际分类意义的 Tab，忽略功能性Tab（如翻页、展开更多）

### 3. 面包屑导航
- 识别页面顶部的面包屑路径
- 通常在 <nav aria-label="breadcrumb"> 或 .breadcrumb 容器内

## 重要规则
- 每个节点必须有 label（显示名称）和 url（跳转链接）
- url 应为相对于当前网站的路径，如 "/news/tech"
- 不完整的链接（如只有 "#" 或 "javascript:void"）请设为空字符串 ""
- children 为空数组表示叶子节点
- level 从 0 开始（0=顶级导航，1=一级分类，2=二级分类...）

## 输出格式
请严格输出以下JSON格式，不要包含任何其他文字：
{
  "navigation": [
    {
      "label": "导航名称",
      "url": "/完整或相对路径",
      "children": [
        {"label": "子分类", "url": "/路径", "children": []}
      ]
    }
  ],
  "tabs": [
    {"label": "Tab名称", "url": "/带参数的URL或空字符串"}
  ],
  "breadcrumb": [
    {"label": "首页", "url": "/"},
    {"label": "新闻", "url": "/news"}
  ]
}
"""


@dataclass
class TabNode:
    """页签节点数据结构"""
    id: str
    label: str
    url: str
    children: List["TabNode"] = field(default_factory=list)
    level: int = 0
    type: str = "nav"  # "nav" | "tab" | "breadcrumb"
    expandable: bool = False
    url_pattern: Optional[str] = None


@dataclass
class TabTree:
    """页签树结构"""
    domain: str
    site_title: str
    root: TabNode
    all_nodes: List[TabNode]
    generated_at: str
    total_count: int


class TabAnalyzer:
    """页签识别分析器"""

    def __init__(self):
        self._node_id_counter = 0

    def _generate_node_id(self) -> str:
        """生成唯一节点ID"""
        self._node_id_counter += 1
        return f"tab-{self._node_id_counter:04d}"

    async def analyze(
        self,
        url: str,
        include_nav: bool = True,
        include_tabs: bool = True,
        max_depth: int = 3
    ) -> Dict[str, Any]:
        """
        分析页面的页签结构

        Args:
            url: 要分析的URL
            include_nav: 是否识别导航栏
            include_tabs: 是否识别内容区Tab
            max_depth: 最大递归深度

        Returns:
            包含 success, tree/error, duration 的字典
        """
        start_time = time.time()

        try:
            # Step 1: 爬取页面
            html, title = await self._fetch_page(url)

            # Step 2: 提取导航和Tab区域HTML
            nav_html, tab_html = self._extract_html_sections(html, url)

            # Step 3: 调用LLM分析
            llm_result = await self._analyze_with_llm(
                url, title, nav_html, tab_html,
                include_nav, include_tabs
            )

            # Step 4: 构建TabTree
            tree = self._build_tab_tree(url, llm_result)

            duration = int((time.time() - start_time) * 1000)
            return {"success": True, "tree": tree, "duration": duration}

        except Exception as e:
            logger.exception(f"页签分析失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "duration": int((time.time() - start_time) * 1000)
            }

    async def _fetch_page(self, url: str) -> tuple[str, str]:
        """使用crawl4ai爬取页面"""
        config = CrawlerRunConfig(
            word_count_threshold=0,
            page_timeout=60000,
            screenshot=False,
        )
        browser_config = BrowserConfig(headless=True, verbose=False)

        async with AsyncWebCrawler(config=browser_config) as crawler:
            result = await crawler.arun(url=url, config=config)

            if not result.success:
                raise Exception(f"页面爬取失败: {result.error_message}")

            return result.html, result.metadata.get("title", "")

    def _extract_html_sections(self, html: str, base_url: str) -> tuple[str, str]:
        """
        提取导航和Tab区域HTML

        Returns:
            (nav_html, tab_html) 元组
        """
        soup = BeautifulSoup(html, "lxml")
        base_domain = urlparse(base_url).netloc

        # 定义导航相关的关键词
        nav_keywords = ["nav", "menu", "header", "topbar", "top-bar", "navbar", "nav-bar", "navigation", "main-nav"]

        nav_html_parts = []
        tab_html_parts = []

        # 1. 提取导航区域
        # 方法1: 查找 <nav> 标签
        for nav in soup.find_all("nav"):
            nav_text = nav.get_text(strip=True)
            if len(nav_text) > 20:  # 过滤空导航
                nav_html_parts.append(str(nav))

        # 方法2: 查找可能包含导航的 header 和 div
        for tag in soup.find_all(["header", "div", "ul"], class_=lambda x: x and any(kw in str(x).lower() for kw in nav_keywords)):
            nav_text = tag.get_text(strip=True)
            if len(nav_text) > 30 and len(tag.find_all("a")) >= 2:  # 至少有2个链接
                nav_html_parts.append(str(tag))

        # 方法3: 查找包含多个链接的列表（通常是菜单）
        for ul in soup.find_all("ul"):
            links = ul.find_all("a")
            if len(links) >= 4:  # 至少有4个链接才认为是导航
                parent = ul.parent
                if parent:
                    nav_html_parts.append(str(parent))
                else:
                    nav_html_parts.append(str(ul))

        # 2. 提取Tab区域
        tab_keywords = ["tab", "switch", "filter", "category", "tag-group", "tabs"]

        for tag in soup.find_all(["div", "ul", "nav"], class_=lambda x: x and any(kw in str(x).lower() for kw in tab_keywords)):
            # 过滤已添加到导航的部分
            tag_text = tag.get_text(strip=True)
            if 10 < len(tag_text) < 500 and len(tag.find_all("a", href=lambda h: h and not h.startswith("#"))) >= 2:
                tab_html_parts.append(str(tag))

        # 3. 提取面包屑
        breadcrumb_parts = []
        for nav in soup.find_all(["nav", "div"], class_=lambda x: x and "breadcrumb" in str(x).lower()):
            breadcrumb_parts.append(str(nav))
        for ol in soup.find_all("ol", class_=lambda x: x and "breadcrumb" in str(x).lower()):
            breadcrumb_parts.append(str(ol))

        # 合并结果，限制大小避免token溢出
        nav_html = "\n".join(nav_html_parts)[:50000]
        tab_html = "\n".join(tab_html_parts)[:30000]
        breadcrumb_html = "\n".join(breadcrumb_parts)[:10000]

        # 合并到 tab_html 中（面包屑也是一种tab）
        if breadcrumb_html:
            tab_html = f"{breadcrumb_html}\n{tab_html}"

        return nav_html, tab_html

    async def _analyze_with_llm(
        self,
        url: str,
        title: str,
        nav_html: str,
        tab_html: str,
        include_nav: bool,
        include_tabs: bool
    ) -> Dict[str, Any]:
        """
        调用LLM分析页签结构

        Returns:
            解析后的JSON结构
        """
        # 构建用户提示
        parts = []

        parts.append(f"网站URL: {url}")
        parts.append(f"网站标题: {title}")
        parts.append("")

        if include_nav and nav_html:
            parts.append("=== 导航区域HTML ===")
            parts.append(nav_html)
            parts.append("")

        if include_tabs and tab_html:
            parts.append("=== Tab/面包屑区域HTML ===")
            parts.append(tab_html)
            parts.append("")

        if not include_nav and not include_tabs:
            parts.append("[提示] 已禁用所有识别，请返回空的 navigation, tabs 和 breadcrumb 数组。")

        user_prompt = "\n".join(parts)

        # 获取默认LLM配置
        config = get_llm_config()
        default_model_id = config.default_llm

        # 调用LLM
        response = await llm_service.non_stream_chat(
            model_id=default_model_id,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,  # 较低的temperature以保持一致性
            max_tokens=4000,
        )

        # 解析JSON响应
        if response.startswith("[错误]"):
            raise Exception(response)

        try:
            # 尝试从响应中提取JSON
            json_str = self._extract_json(response)
            result = json.loads(json_str)

            # 验证并标准化结果
            return self._normalize_result(result, url)

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败，尝试修复: {e}")
            # 尝试修复常见的JSON问题
            try:
                # 移除可能的 markdown 代码块标记
                json_str = re.sub(r'^```json\s*', '', json_str)
                json_str = re.sub(r'^```\s*', '', json_str)
                json_str = re.sub(r'\s*```$', '', json_str)
                result = json.loads(json_str)
                return self._normalize_result(result, url)
            except:
                raise Exception(f"LLM返回格式错误，无法解析为JSON: {response[:500]}")

    def _extract_json(self, text: str) -> str:
        """从文本中提取JSON字符串"""
        # 方法1: 查找 ```json ... ``` 包裹的代码块
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            return match.group(1).strip()

        # 方法2: 查找 {...} 包裹的JSON
        match = re.search(r'(\{[\s\S]*\})', text)
        if match:
            return match.group(1)

        # 方法3: 返回原文本，让json.loads处理
        return text

    def _normalize_result(self, result: Dict, base_url: str) -> Dict:
        """标准化LLM返回的结果"""
        normalized = {
            "navigation": [],
            "tabs": [],
            "breadcrumb": []
        }

        # 处理 navigation
        for item in result.get("navigation", []):
            normalized_item = self._normalize_nav_item(item, base_url, 0)
            if normalized_item:
                normalized["navigation"].append(normalized_item)

        # 处理 tabs
        for item in result.get("tabs", []):
            if item.get("label"):
                url = self._normalize_url(item.get("url", ""), base_url)
                normalized["tabs"].append({
                    "label": item.get("label", "")[:100],
                    "url": url
                })

        # 处理 breadcrumb
        for item in result.get("breadcrumb", []):
            if item.get("label"):
                url = self._normalize_url(item.get("url", ""), base_url)
                normalized["breadcrumb"].append({
                    "label": item.get("label", "")[:100],
                    "url": url
                })

        return normalized

    def _normalize_nav_item(self, item: Dict, base_url: str, level: int) -> Optional[Dict]:
        """标准化导航项"""
        label = item.get("label", "").strip()
        if not label:
            return None

        url = self._normalize_url(item.get("url", ""), base_url)

        # 递归处理子节点
        children = []
        for child in item.get("children", []):
            child_item = self._normalize_nav_item(child, base_url, level + 1)
            if child_item:
                children.append(child_item)

        return {
            "label": label[:100],  # 限制长度
            "url": url,
            "children": children,
            "level": level
        }

    def _normalize_url(self, url: str, base_url: str) -> str:
        """标准化URL，返回完整绝对URL"""
        if not url or url in ["#", "javascript:void(0)", "javascript:;", ""]:
            return ""

        url = url.strip()

        # 如果是完整URL，直接返回
        if url.startswith("http://") or url.startswith("https://"):
            return url

        # 如果是相对路径（以 / 开头），拼接域名
        if url.startswith("/"):
            parsed = urlparse(base_url)
            scheme = parsed.scheme or "https"
            return f"{scheme}://{parsed.netloc}{url}"

        # 如果是相对路径（不是以 / 开头），拼接域名
        if not url.startswith("//"):
            parsed = urlparse(base_url)
            scheme = parsed.scheme or "https"
            base_path = parsed.path.rsplit('/', 1)[0] if parsed.path != '/' else ''
            return f"{scheme}://{parsed.netloc}{base_path}/{url}"

        # 否则返回原样
        return url

    def _build_tab_tree(self, url: str, llm_result: Dict) -> TabTree:
        """从LLM结果构建TabTree"""
        self._node_id_counter = 0  # 重置计数器

        # 获取网站信息
        parsed = urlparse(url)
        domain = parsed.netloc
        site_title = llm_result.get("site_title", domain)

        # 构建根节点
        root = TabNode(
            id=self._generate_node_id(),
            label="全部",
            url="/",
            children=[],
            level=0,
            type="nav"
        )

        all_nodes = [root]

        # 处理导航 - 作为顶级分类
        for nav_item in llm_result.get("navigation", []):
            node = self._parse_nav_item(nav_item)
            if node:
                self._flatten_nodes(node, all_nodes)
                root.children.append(node)

        # 处理面包屑 - 插入导航之前
        breadcrumbs = llm_result.get("breadcrumb", [])
        if breadcrumbs:
            breadcrumb_parent = root
            for crumb in breadcrumbs:
                crumb_node = TabNode(
                    id=self._generate_node_id(),
                    label=crumb.get("label", ""),
                    url=crumb.get("url", ""),
                    children=[],
                    level=1,
                    type="breadcrumb",
                    expandable=False
                )
                all_nodes.append(crumb_node)
                # 面包屑不添加到root.children，而是作为导航的补充说明

        # 处理Tab - 作为额外选项
        tabs = llm_result.get("tabs", [])
        if tabs:
            tab_group_node = TabNode(
                id=self._generate_node_id(),
                label="内容Tab",
                url="",
                children=[],
                level=1,
                type="nav",
                expandable=True
            )

            for tab in tabs:
                if tab.get("label"):
                    tab_node = TabNode(
                        id=self._generate_node_id(),
                        label=tab.get("label", ""),
                        url=tab.get("url", ""),
                        children=[],
                        level=2,
                        type="tab",
                        expandable=False
                    )
                    all_nodes.append(tab_node)
                    tab_group_node.children.append(tab_node)

            if tab_group_node.children:
                all_nodes.append(tab_group_node)
                root.children.append(tab_group_node)
                tab_group_node.expandable = True

        return TabTree(
            domain=domain,
            site_title=site_title or domain,
            root=root,
            all_nodes=all_nodes,
            generated_at=datetime.now().isoformat(),
            total_count=len(all_nodes)
        )

    def _parse_nav_item(self, item: Dict, level: int = 0) -> Optional[TabNode]:
        """递归解析导航项"""
        label = item.get("label", "")
        if not label:
            return None

        children = []
        for child in item.get("children", []):
            child_node = self._parse_nav_item(child, level + 1)
            if child_node:
                children.append(child_node)

        return TabNode(
            id=self._generate_node_id(),
            label=label,
            url=item.get("url", ""),
            children=children,
            level=level,
            type="nav",
            expandable=len(children) > 0
        )

    def _flatten_nodes(self, node: TabNode, all_nodes: List[TabNode]):
        """扁平化所有节点"""
        all_nodes.append(node)
        for child in node.children:
            self._flatten_nodes(child, all_nodes)


# 全局服务实例
tab_analyzer = TabAnalyzer()