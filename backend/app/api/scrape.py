"""
网页爬取 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, List, Literal
from datetime import datetime, date
import asyncio
import json

# 全局取消事件管理器
class CancelManager:
    """爬取取消管理器"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._cancel_event = asyncio.Event()
            cls._instance._current_scrape_id = None
        return cls._instance

    def start_scrape(self, scrape_id: str):
        """开始新的爬取，清除之前的取消状态"""
        self._cancel_event.clear()
        self._current_scrape_id = scrape_id

    def cancel(self):
        """取消当前爬取"""
        self._cancel_event.set()
        return self._cancel_event

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def get_cancel_event(self) -> asyncio.Event:
        return self._cancel_event


cancel_manager = CancelManager()

from app.services.scraper import get_scraper, ScrapeOptions, ScrapedResult

router = APIRouter(prefix="/scrape", tags=["网页爬取"])


class ScrapeRequest(BaseModel):
    """爬取请求"""
    url: str
    options: Optional[ScrapeOptions] = None


class ScrapeBatchRequest(BaseModel):
    """批量爬取请求"""
    urls: List[str]
    options: Optional[ScrapeOptions] = None


class ScrapeSourcesRequest(BaseModel):
    """从配置源爬取请求"""
    source_ids: Optional[List[str]] = None
    options: Optional[ScrapeOptions] = None


class ScrapedResultResponse(BaseModel):
    """爬取结果响应"""
    url: str
    title: str
    content: str
    html: str
    word_count: int
    links: List[str]
    status: str
    error_message: Optional[str] = None
    scraped_at: str
    published_at: Optional[str] = None
    author: Optional[str] = None
    summary: Optional[str] = None
    keywords: List[str] = []


def _result_to_response(result: ScrapedResult) -> ScrapedResultResponse:
    """转换爬取结果为响应模型"""
    return ScrapedResultResponse(
        url=result.url,
        title=result.title,
        content=result.content,
        html=result.html,
        word_count=result.word_count,
        links=result.links,
        status=result.status,
        error_message=result.error_message,
        scraped_at=result.scraped_at,
        published_at=result.published_at,
        author=result.author,
        summary=result.summary,
        keywords=result.keywords,
    )


@router.post("")
async def scrape_url(request: ScrapeRequest):
    """爬取单个网页"""
    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    result = await scraper.scrape(request.url, options)
    return _result_to_response(result)


@router.post("/batch")
async def scrape_batch(request: ScrapeBatchRequest):
    """批量爬取多个网页"""
    if not request.urls:
        raise HTTPException(status_code=400, detail="URL 列表不能为空")

    if len(request.urls) > 50:
        raise HTTPException(status_code=400, detail="最多同时爬取 50 个 URL")

    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    results = await scraper.scrape_batch(request.urls, options)
    return [_result_to_response(r) for r in results]


@router.post("/sources")
async def scrape_sources(request: ScrapeSourcesRequest):
    """从配置的爬取源爬取"""
    from app.api.settings import settings_store

    sources = settings_store.get_settings().get("scrape_sources", [])
    enabled_sources = [s for s in sources if s.get("is_enabled", True)]

    if request.source_ids:
        enabled_sources = [s for s in enabled_sources if s.get("id") in request.source_ids]

    if not enabled_sources:
        raise HTTPException(status_code=404, detail="没有找到启用的爬取源")

    urls = [s["url"] for s in enabled_sources]
    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    results = await scraper.scrape_batch(urls, options)

    return [_result_to_response(r) for r in results]


@router.get("/sources")
async def get_scrape_sources():
    """获取所有爬取源列表"""
    from app.api.settings import settings_store
    sources = settings_store.get_settings().get("scrape_sources", [])
    return sources


@router.get("/test")
async def test_scrape():
    """测试爬取功能"""
    scraper = get_scraper()
    result = await scraper.scrape("https://httpbin.org/html")
    return _result_to_response(result)


class DateRangeModel(BaseModel):
    """日期范围模型"""
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class ScrapeDeepRequest(BaseModel):
    """深度爬取请求"""
    url: str
    options: Optional[ScrapeOptions] = None
    max_articles: int = 10
    date_range: Optional[Literal["today", "week", "month"]] = None
    custom_date_range: Optional[DateRangeModel] = None
    scrape_level: Optional[Literal["list", "detail", "deep"]] = "deep"
    scrape_id: Optional[str] = None


class DeepScrapeResponse(BaseModel):
    """深度爬取响应"""
    scrape_id: str
    status: str
    error_message: Optional[str] = None
    list_page: Optional[ScrapedResultResponse] = None
    articles: List[ScrapedResultResponse] = []
    total_articles: int = 0


@router.post("/deep", response_model=DeepScrapeResponse)
async def scrape_deep(request: ScrapeDeepRequest):
    """
    深度爬取：在后台线程执行爬取，立即返回 scrape_id

    前端获取 scrape_id 后，轮询 /scrape/progress/{scrape_id} 获取实时进度
    """
    from app.services.scraper import WebScraper, scrape_logger, progress_manager
    import logging
    from concurrent.futures import ThreadPoolExecutor

    api_logger = logging.getLogger(__name__)
    api_logger.info(f"[DEBUG] 接收请求: url={request.url}, date_range={request.date_range}, scrape_level={request.scrape_level}")

    # 生成 scrape_id
    import uuid
    scrape_id = request.scrape_id or str(uuid.uuid4())[:8]

    # 初始化进度状态
    progress_manager.set_progress(scrape_id, {
        "status": "starting",
        "stage": 0,
        "stage_name": "正在启动...",
        "stage_detail": "准备爬取任务",
        "current": 0,
        "total": 0,
    })

    # 启动爬取并设置取消管理器
    cancel_manager.start_scrape(scrape_id)

    options = request.options or ScrapeOptions()
    max_articles = min(request.max_articles, 50)

    # 解析自定义日期范围
    custom_range = None
    if request.custom_date_range:
        start_dt = None
        end_dt = None

        if request.custom_date_range.start_date:
            start_dt = datetime.strptime(request.custom_date_range.start_date, "%Y-%m-%d").date()
        if request.custom_date_range.end_date:
            end_dt = datetime.strptime(request.custom_date_range.end_date, "%Y-%m-%d").date()

        # 确保起始日期 <= 结束日期（如果用户输反了，自动交换）
        if start_dt and end_dt and start_dt > end_dt:
            api_logger.warning(f"日期范围输入反了，自动交换: start={start_dt}, end={end_dt}")
            start_dt, end_dt = end_dt, start_dt

        custom_range = {
            "start_date": start_dt,
            "end_date": end_dt,
        }

    def do_scrape():
        """在后台线程中执行爬取"""
        try:
            # 创建新的事件循环
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                scraper = WebScraper(cancel_event=cancel_manager.get_cancel_event())

                # 进度回调函数
                def update_progress(stage: int, stage_name: str, stage_detail: str = "", current: int = 0, total: int = 0):
                    progress_manager.set_progress(scrape_id, {
                        "status": "scraping",
                        "stage": stage,
                        "stage_name": stage_name,
                        "stage_detail": stage_detail,
                        "current": current,
                        "total": total,
                    })

                # 更新进度：开始解析列表页
                update_progress(1, "正在解析列表页", f"访问 {request.url}")

                # 执行爬取
                list_page_result, article_results = loop.run_until_complete(
                    scraper.deep_scrape(
                        url=request.url,
                        options=options,
                        max_articles=max_articles,
                        date_range=request.date_range,
                        custom_date_range=custom_range,
                        scrape_level=request.scrape_level,
                        scrape_id=scrape_id,
                        progress_callback=update_progress
                    )
                )

                # 保存结果到进度管理器
                progress_manager.set_progress(scrape_id, {
                    "status": "completed",
                    "stage": 5,
                    "stage_name": "已完成",
                    "stage_detail": f"成功爬取 {len(article_results)} 篇文章",
                    "current": len(article_results),
                    "total": len(article_results),
                    "results": {
                        "list_page": _result_to_response(list_page_result).__dict__ if list_page_result else None,
                        "articles": [_result_to_response(r).__dict__ for r in article_results],
                        "total_articles": len(article_results),
                    }
                })

            finally:
                loop.close()
        except Exception as e:
            api_logger.error(f"后台爬取异常: {e}")
            progress_manager.set_progress(scrape_id, {
                "status": "error",
                "stage": -1,
                "stage_name": "爬取失败",
                "stage_detail": str(e),
                "current": 0,
                "total": 0,
                "error": str(e),
            })

    # 在后台线程执行爬取
    executor = ThreadPoolExecutor(max_workers=1)
    executor.submit(do_scrape)

    # 立即返回 scrape_id，前端可以轮询进度
    return DeepScrapeResponse(
        scrape_id=scrape_id,
        status="started",
        list_page=None,
        articles=[],
        total_articles=0
    )


@router.get("/progress/{scrape_id}")
async def get_progress(scrape_id: str):
    """获取爬取进度（轮询端点）"""
    from app.services.scraper import progress_manager
    progress = progress_manager.get_progress(scrape_id)
    # 如果没有进度记录，返回默认状态
    if not progress:
        return {
            "status": "not_found",
            "stage": 0,
            "stage_name": "未知",
            "stage_detail": "任务不存在或已过期",
            "current": 0,
            "total": 0,
        }
    return progress


@router.post("/cancel")
async def cancel_scrape():
    """取消当前正在进行的爬取任务"""
    if cancel_manager.is_cancelled:
        return {"status": "already_cancelled", "message": "爬取已经在取消中"}

    cancel_manager.cancel()
    progress_manager.emit("cancel", "cancelled", {"message": "爬取已取消"})
    return {"status": "cancelled", "message": "已发送取消信号"}


# ==================== 页签识别 API ====================

from app.schemas.tab_schema import (
    TabAnalyzeRequest, TabAnalyzeResponse,
    TabNodeModel, TabTreeModel
)
from app.services.tab_analyzer import TabAnalyzer, TabNode, TabTree


def _node_to_model(node: TabNode) -> TabNodeModel:
    """将内部 TabNode 转换为 Pydantic 模型"""
    return TabNodeModel(
        id=node.id,
        label=node.label,
        url=node.url,
        children=[_node_to_model(c) for c in node.children] if node.children else [],
        level=node.level,
        type=node.type,
        expandable=node.expandable,
        url_pattern=node.url_pattern,
    )


def _tree_to_model(tree: TabTree) -> TabTreeModel:
    """将内部 TabTree 转换为 Pydantic 模型"""
    return TabTreeModel(
        domain=tree.domain,
        site_title=tree.site_title,
        root=_node_to_model(tree.root),
        all_nodes=[_node_to_model(n) for n in tree.all_nodes],
        generated_at=tree.generated_at,
        total_count=tree.total_count,
    )


@router.post("/tabs", response_model=TabAnalyzeResponse)
async def analyze_tabs(request: TabAnalyzeRequest):
    """分析页面的页签结构，返回分类树"""
    analyzer = TabAnalyzer()

    result = await analyzer.analyze(
        url=request.url,
        include_nav=request.include_nav,
        include_tabs=request.include_tabs,
        max_depth=request.max_depth,
    )

    if result["success"]:
        return TabAnalyzeResponse(
            success=True,
            tree=_tree_to_model(result["tree"]),
            duration=result["duration"],
        )
    else:
        return TabAnalyzeResponse(
            success=False,
            error=result["error"],
            duration=result["duration"],
        )