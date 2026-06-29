"""设置相关的 Pydantic Schema 定义"""
from typing import Optional, List
from pydantic import BaseModel


class ScrapeSourceRequest(BaseModel):
    """爬取源请求"""
    name: str
    url: str
    category: str = "business"  # government | business | academic
    description: Optional[str] = None
    is_enabled: bool = True


class ScrapeSourceResponse(BaseModel):
    """爬取源响应"""
    id: str
    name: str
    url: str
    category: str
    description: Optional[str] = None
    is_enabled: bool
    created_at: str
    updated_at: str


class SettingsResponse(BaseModel):
    """设置响应"""
    theme: str = "dark"
    primary_color: str = "indigo"
    scrape_sources: List[ScrapeSourceResponse] = []


class SaveSettingsRequest(BaseModel):
    """保存设置请求"""
    theme: Optional[str] = None
    primary_color: Optional[str] = None
    scrape_sources: Optional[List[ScrapeSourceRequest]] = None