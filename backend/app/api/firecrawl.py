"""
Firecrawl API 路由
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List

from app.services.firecrawl_service import get_firecrawl_service, FirecrawlService

router = APIRouter(prefix="/firecrawl", tags=["Firecrawl"])


class ScrapeRequest(BaseModel):
    """爬取请求"""
    url: str = Field(..., description="网页 URL")
    formats: Optional[List[str]] = Field(
        default=["markdown", "html", "links"],
        description="输出格式: markdown, html, links, screenshot"
    )


class ScrapeResponse(BaseModel):
    """爬取响应"""
    success: bool
    url: str
    title: str = ""
    content: str = ""
    html: str = ""
    word_count: int = 0
    links: List[str] = []
    status: str = ""
    error_message: Optional[str] = None


class MapRequest(BaseModel):
    """网站地图请求"""
    url: str = Field(..., description="网站 URL")


class MapResponse(BaseModel):
    """网站地图响应"""
    success: bool
    url: str
    links: List[str] = []
    metadata: dict = {}
    error_message: Optional[str] = None


class HealthResponse(BaseModel):
    """健康检查响应"""
    available: bool
    url: str
    message: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """检查 Firecrawl 服务是否可用"""
    service = get_firecrawl_service()
    is_available = service.is_available()

    return HealthResponse(
        available=is_available,
        url=service.api_url,
        message="Firecrawl 服务运行正常" if is_available else "Firecrawl 服务不可用"
    )


@router.post("/scrape", response_model=ScrapeResponse)
async def scrape_url(request: ScrapeRequest):
    """
    爬取网页内容

    - **url**: 要爬取的网页地址
    - **formats**: 输出格式列表，可选 markdown, html, links, screenshot
    """
    service = get_firecrawl_service()

    try:
        result = service.scrape(request.url, request.formats)

        return ScrapeResponse(
            success=result.status == "success",
            url=result.url,
            title=result.title,
            content=result.content,
            html=result.html,
            word_count=result.word_count,
            links=result.links,
            status=result.status,
            error_message=result.error_message
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"爬取失败: {str(e)}")


@router.post("/map", response_model=MapResponse)
async def get_sitemap(request: MapRequest):
    """
    获取网站地图

    返回网站的所有链接
    """
    service = get_firecrawl_service()

    try:
        result = service.map(request.url)

        return MapResponse(
            success=result.get("status") == "success",
            url=request.url,
            links=result.get("links", []),
            metadata=result.get("metadata", {}),
            error_message=result.get("error_message")
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取地图失败: {str(e)}")