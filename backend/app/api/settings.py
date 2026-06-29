from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter(prefix="/settings", tags=["设置"])


# ============ 请求/响应模型 ============

class ScrapeSourceRequest(BaseModel):
    name: str
    url: str
    category: str = "business"  # government | business | academic
    description: Optional[str] = None
    is_enabled: bool = True


class ScrapeSourceResponse(BaseModel):
    id: str
    name: str
    url: str
    category: str
    description: Optional[str] = None
    is_enabled: bool
    created_at: str
    updated_at: str


class SettingsResponse(BaseModel):
    theme: str = "dark"
    primary_color: str = "indigo"
    scrape_sources: List[ScrapeSourceResponse] = []


class SaveSettingsRequest(BaseModel):
    theme: Optional[str] = None
    primary_color: Optional[str] = None
    scrape_sources: Optional[List[ScrapeSourceRequest]] = None


# ============ 内存存储（生产环境应使用数据库）============

class SettingsStore:
    def __init__(self):
        self.settings = {
            "theme": "dark",
            "primary_color": "indigo",
        }
        self.scrape_sources = {}
        self._source_counter = 0

    def get_settings(self) -> dict:
        sources = []
        for source_id, source in self.scrape_sources.items():
            sources.append(ScrapeSourceResponse(
                id=source["id"],
                name=source["name"],
                url=source["url"],
                category=source["category"],
                description=source.get("description"),
                is_enabled=source["is_enabled"],
                created_at=source["created_at"],
                updated_at=source["updated_at"],
            ))
        return {
            **self.settings,
            "scrape_sources": sorted(sources, key=lambda x: x.created_at, reverse=True),
        }

    def update_settings(self, data: dict):
        if "theme" in data and data["theme"]:
            self.settings["theme"] = data["theme"]
        if "primary_color" in data and data["primary_color"]:
            self.settings["primary_color"] = data["primary_color"]

    def add_scrape_source(self, source: dict) -> ScrapeSourceResponse:
        self._source_counter += 1
        source_id = f"src_{self._source_counter}_{int(datetime.now().timestamp())}"
        now = datetime.now().isoformat()
        new_source = {
            "id": source_id,
            "name": source["name"],
            "url": source["url"],
            "category": source.get("category", "business"),
            "description": source.get("description"),
            "is_enabled": source.get("is_enabled", True),
            "created_at": now,
            "updated_at": now,
        }
        self.scrape_sources[source_id] = new_source
        return ScrapeSourceResponse(**new_source)

    def update_scrape_source(self, source_id: str, updates: dict) -> Optional[ScrapeSourceResponse]:
        if source_id not in self.scrape_sources:
            return None
        source = self.scrape_sources[source_id]
        for key, value in updates.items():
            if key != "id" and key != "created_at":
                source[key] = value
        source["updated_at"] = datetime.now().isoformat()
        return ScrapeSourceResponse(**source)

    def delete_scrape_source(self, source_id: str) -> bool:
        if source_id in self.scrape_sources:
            del self.scrape_sources[source_id]
            return True
        return False

    def toggle_scrape_source(self, source_id: str) -> Optional[ScrapeSourceResponse]:
        if source_id not in self.scrape_sources:
            return None
        source = self.scrape_sources[source_id]
        source["is_enabled"] = not source["is_enabled"]
        source["updated_at"] = datetime.now().isoformat()
        return ScrapeSourceResponse(**source)


# 全局存储实例
settings_store = SettingsStore()


# ============ API 路由 ============

@router.get("", response_model=SettingsResponse)
async def get_settings():
    """获取所有设置"""
    return settings_store.get_settings()


@router.put("")
async def save_settings(request: SaveSettingsRequest):
    """保存设置"""
    data = request.model_dump(exclude_none=True)
    settings_store.update_settings(data)
    return {"message": "设置已保存"}


# 爬取源 CRUD
@router.get("/scrape", response_model=List[ScrapeSourceResponse])
async def list_scrape_sources():
    """获取所有爬取源"""
    result = settings_store.get_settings()
    return result["scrape_sources"]


@router.post("/scrape", response_model=ScrapeSourceResponse)
async def add_scrape_source(source: ScrapeSourceRequest):
    """添加爬取源"""
    return settings_store.add_scrape_source(source.model_dump())


@router.put("/scrape/{source_id}", response_model=ScrapeSourceResponse)
async def update_scrape_source(source_id: str, source: ScrapeSourceRequest):
    """更新爬取源"""
    result = settings_store.update_scrape_source(source_id, source.model_dump())
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="爬取源不存在")
    return result


@router.delete("/scrape/{source_id}")
async def delete_scrape_source(source_id: str):
    """删除爬取源"""
    if not settings_store.delete_scrape_source(source_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="爬取源不存在")
    return {"message": "爬取源已删除"}


@router.post("/scrape/{source_id}/toggle", response_model=ScrapeSourceResponse)
async def toggle_scrape_source(source_id: str):
    """切换爬取源启用状态"""
    result = settings_store.toggle_scrape_source(source_id)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="爬取源不存在")
    return result