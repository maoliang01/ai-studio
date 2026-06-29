"""爬取相关的 Pydantic Schema 定义"""
from typing import Optional, List
from pydantic import BaseModel


class ScrapeOptions(BaseModel):
    """爬取选项"""
    extract_content: bool = True
    fetch_html: bool = False
    preserve_format: bool = False
    max_depth: int = 0
    timeout: int = 30


class ScrapeRequest(BaseModel):
    """单个 URL 爬取请求"""
    url: str
    options: Optional[ScrapeOptions] = None


class ScrapeResponse(BaseModel):
    """爬取响应"""
    url: str
    title: str
    content: str
    html: Optional[str] = ""
    word_count: int
    links: List[str] = []
    status: str  # "success" | "error"
    error_message: Optional[str] = None
    scraped_at: str


class BatchScrapeRequest(BaseModel):
    """批量爬取请求"""
    urls: List[str]
    options: Optional[ScrapeOptions] = None


class SourceScrapeRequest(BaseModel):
    """从配置的爬取源爬取请求"""
    source_ids: Optional[List[str]] = None  # 空列表表示爬取所有启用的源
    options: Optional[ScrapeOptions] = None