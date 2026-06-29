"""
网页爬取 API
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, List

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
    source_ids: Optional[List[str]] = None  # 如果为空，则爬取所有启用的源
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
    # 新增：文章元信息
    published_at: Optional[str] = None  # 发布时间
    author: Optional[str] = None  # 作者
    summary: Optional[str] = None  # 内容摘要
    keywords: List[str] = []  # 关键字标签


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


@router.post("", response_model=ScrapedResultResponse)
async def scrape_url(request: ScrapeRequest):
    """
    爬取单个网页

    Args:
        request: 包含 URL 和可选配置

    Returns:
        ScrapedResultResponse: 爬取结果
    """
    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    result = await scraper.scrape(request.url, options)
    return _result_to_response(result)


@router.post("/batch", response_model=List[ScrapedResultResponse])
async def scrape_batch(request: ScrapeBatchRequest):
    """
    批量爬取多个网页

    Args:
        request: 包含 URL 列表和可选配置

    Returns:
        List[ScrapedResultResponse]: 爬取结果列表
    """
    if not request.urls:
        raise HTTPException(status_code=400, detail="URL 列表不能为空")

    if len(request.urls) > 50:
        raise HTTPException(status_code=400, detail="最多同时爬取 50 个 URL")

    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    results = await scraper.scrape_batch(request.urls, options)
    return [_result_to_response(r) for r in results]


@router.post("/sources", response_model=List[ScrapedResultResponse])
async def scrape_sources(request: ScrapeSourcesRequest):
    """
    从配置的爬取源爬取

    Args:
        request: 包含源 ID 列表和可选配置

    Returns:
        List[ScrapedResultResponse]: 爬取结果列表
    """
    # 这里需要从 settings store 获取爬取源配置
    # 由于是内存存储，需要通过 appstate 获取
    from app.main import appstate

    sources = appstate.settings.get("scrape_sources", [])

    # 过滤启用的源
    enabled_sources = [s for s in sources if s.get("is_enabled", True)]

    # 如果指定了 source_ids，进一步过滤
    if request.source_ids:
        enabled_sources = [s for s in enabled_sources if s.get("id") in request.source_ids]

    if not enabled_sources:
        raise HTTPException(status_code=404, detail="没有找到启用的爬取源")

    urls = [s["url"] for s in enabled_sources]
    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    results = await scraper.scrape_batch(urls, options)

    return [_result_to_response(r) for r in results]


@router.get("/sources", response_model=List[dict])
async def get_scrape_sources():
    """获取所有爬取源列表"""
    from app.main import appstate
    sources = appstate.settings.get("scrape_sources", [])
    return sources


@router.get("/test")
async def test_scrape():
    """测试爬取功能（爬取一个简单的测试页面）"""
    scraper = get_scraper()
    # 使用 httpbin 作为测试
    result = await scraper.scrape("https://httpbin.org/html")
    return _result_to_response(result)


class ScrapeDeepRequest(BaseModel):
    """深度爬取请求"""
    url: str
    options: Optional[ScrapeOptions] = None
    max_articles: int = 10  # 最多爬取的文章数量


class DeepScrapeResponse(BaseModel):
    """深度爬取响应"""
    list_page: ScrapedResultResponse  # 列表页结果
    articles: List[ScrapedResultResponse]  # 文章结果列表
    total_articles: int  # 总共爬取的文章数


@router.post("/deep", response_model=DeepScrapeResponse)
async def scrape_deep(request: ScrapeDeepRequest):
    """
    深度爬取：从列表页自动识别文章链接并爬取正文

    工作流程：
    1. 爬取列表页
    2. 使用 LLM 识别文章链接（过滤非文章链接）
    3. 并发爬取每个文章的正文内容
    4. 为每篇文章单独提取元信息

    Args:
        request: 包含列表页 URL 和配置

    Returns:
        DeepScrapeResponse: 包含列表页和所有文章的爬取结果
    """
    scraper = get_scraper()
    options = request.options or ScrapeOptions()
    max_articles = min(request.max_articles, 50)  # 最多50篇

    list_page_result, article_results = await scraper.deep_scrape(
        url=request.url,
        options=options,
        max_articles=max_articles
    )

    return DeepScrapeResponse(
        list_page=_result_to_response(list_page_result),
        articles=[_result_to_response(r) for r in article_results],
        total_articles=len(article_results)
    )