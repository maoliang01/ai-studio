"""Pydantic Schema 定义模块"""
from app.schemas.chat import (
    Message,
    ChatRequest,
    ChatResponse,
    ModelInfo,
    ModelConfigRequest,
    TestResult,
)
from app.schemas.settings import (
    ScrapeSourceRequest,
    ScrapeSourceResponse,
    SettingsResponse,
    SaveSettingsRequest,
)
from app.schemas.scrape import (
    ScrapeOptions,
    ScrapeRequest,
    ScrapeResponse,
    BatchScrapeRequest,
    SourceScrapeRequest,
)

__all__ = [
    # Chat
    "Message",
    "ChatRequest",
    "ChatResponse",
    "ModelInfo",
    "ModelConfigRequest",
    "TestResult",
    # Settings
    "ScrapeSourceRequest",
    "ScrapeSourceResponse",
    "SettingsResponse",
    "SaveSettingsRequest",
    # Scrape
    "ScrapeOptions",
    "ScrapeRequest",
    "ScrapeResponse",
    "BatchScrapeRequest",
    "SourceScrapeRequest",
]