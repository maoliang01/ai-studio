from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
import os
from pathlib import Path

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


# ============ Firecrawl 本地服务配置 ============

class FirecrawlConfig(BaseModel):
    """Firecrawl 配置"""
    use_local: bool = False                    # 是否使用本地服务
    local_url: str = "http://localhost:3002"  # 本地服务地址
    api_key: Optional[str] = "local"          # API Key（本地模式可填 local）
    auto_start: bool = True                   # 爬取时自动启动本地服务


class FirecrawlStatus(BaseModel):
    """Firecrawl 服务状态"""
    is_running: bool = False
    local_url: str = "http://localhost:3002"
    version: Optional[str] = None


class SettingsResponse(BaseModel):
    theme: str = "dark"
    primary_color: str = "indigo"
    scrape_sources: List[ScrapeSourceResponse] = []
    firecrawl: FirecrawlConfig = FirecrawlConfig()


class SaveSettingsRequest(BaseModel):
    theme: Optional[str] = None
    primary_color: Optional[str] = None
    scrape_sources: Optional[List[ScrapeSourceRequest]] = None
    firecrawl: Optional[FirecrawlConfig] = None


# ============ 文件持久化存储 ============

SETTINGS_FILE = Path(__file__).parent.parent.parent / "data" / "settings.json"


class SettingsStore:
    def __init__(self):
        self.settings = {
            "theme": "dark",
            "primary_color": "indigo",
            "firecrawl": FirecrawlConfig().model_dump(),
        }
        self.scrape_sources = {}
        self._source_counter = 0
        self._load_from_file()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _load_from_file(self):
        """从文件加载配置"""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings = data.get("settings", self.settings)
                    self.scrape_sources = data.get("scrape_sources", {})
                    # 更新计数器到最大值
                    for source_id in self.scrape_sources.keys():
                        try:
                            parts = source_id.split("_")
                            if len(parts) >= 2:
                                counter = int(parts[1])
                                if counter > self._source_counter:
                                    self._source_counter = counter
                        except:
                            pass
                    # 确保 firecrawl 配置存在
                    if "firecrawl" not in self.settings:
                        self.settings["firecrawl"] = FirecrawlConfig().model_dump()
            except Exception as e:
                print(f"加载配置文件失败: {e}")

    def _save_to_file(self):
        """保存配置到文件"""
        self._ensure_data_dir()
        try:
            data = {
                "settings": self.settings,
                "scrape_sources": self.scrape_sources,
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

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
            "firecrawl": self.settings.get("firecrawl", FirecrawlConfig().model_dump()),
        }

    def update_settings(self, data: dict):
        if "theme" in data and data["theme"]:
            self.settings["theme"] = data["theme"]
        if "primary_color" in data and data["primary_color"]:
            self.settings["primary_color"] = data["primary_color"]
        if "firecrawl" in data and data["firecrawl"]:
            self.settings["firecrawl"] = data["firecrawl"]
        self._save_to_file()

    def get_firecrawl_config(self) -> FirecrawlConfig:
        """获取 Firecrawl 配置"""
        config_data = self.settings.get("firecrawl", FirecrawlConfig().model_dump())
        return FirecrawlConfig(**config_data)

    def update_firecrawl_config(self, config: dict) -> FirecrawlConfig:
        """更新 Firecrawl 配置"""
        self.settings["firecrawl"] = config
        self._save_to_file()
        return FirecrawlConfig(**config)

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
        self._save_to_file()
        return ScrapeSourceResponse(**new_source)

    def update_scrape_source(self, source_id: str, updates: dict) -> Optional[ScrapeSourceResponse]:
        if source_id not in self.scrape_sources:
            return None
        source = self.scrape_sources[source_id]
        for key, value in updates.items():
            if key != "id" and key != "created_at":
                source[key] = value
        source["updated_at"] = datetime.now().isoformat()
        self._save_to_file()
        return ScrapeSourceResponse(**source)

    def delete_scrape_source(self, source_id: str) -> bool:
        if source_id in self.scrape_sources:
            del self.scrape_sources[source_id]
            self._save_to_file()
            return True
        return False

    def toggle_scrape_source(self, source_id: str) -> Optional[ScrapeSourceResponse]:
        if source_id not in self.scrape_sources:
            return None
        source = self.scrape_sources[source_id]
        source["is_enabled"] = not source["is_enabled"]
        source["updated_at"] = datetime.now().isoformat()
        self._save_to_file()
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


# ============ Firecrawl 配置 API ============

@router.get("/firecrawl", response_model=FirecrawlConfig)
async def get_firecrawl_config():
    """获取 Firecrawl 配置"""
    return settings_store.get_firecrawl_config()


@router.put("/firecrawl", response_model=FirecrawlConfig)
async def update_firecrawl_config(config: FirecrawlConfig):
    """更新 Firecrawl 配置"""
    return settings_store.update_firecrawl_config(config.model_dump())


@router.get("/firecrawl/status", response_model=FirecrawlStatus)
async def get_firecrawl_status():
    """检查 Firecrawl 服务状态"""
    import httpx

    config = settings_store.get_firecrawl_config()
    status = FirecrawlStatus(local_url=config.local_url)

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 尝试调用抓取 API 来检测服务是否可用
            response = await client.post(
                f"{config.local_url}/v1/scrape",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json={"url": "https://example.com", "formats": ["markdown"]}
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("success"):
                    status.is_running = True
                    # 从返回数据中获取一些信息
                    metadata = data.get("data", {}).get("metadata", {})
                    if metadata.get("scrapeId"):
                        status.version = "running"
    except Exception:
        pass
        status.is_running = False

    return status


class FirecrawlStartRequest(BaseModel):
    """启动 Firecrawl 请求"""
    auto_start_local: bool = False  # 是否同时启动本地 Docker 服务


@router.post("/firecrawl/start")
async def start_firecrawl_service(request: FirecrawlStartRequest):
    """检查并提示启动 Firecrawl 服务"""
    import httpx

    config = settings_store.get_firecrawl_config()
    status = FirecrawlStatus(local_url=config.local_url)

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{config.local_url}/docs")
            if response.status_code == 200:
                status.is_running = True
                return {
                    "status": "running",
                    "message": "Firecrawl 服务正在运行",
                    "url": config.local_url,
                }
    except Exception:
        pass

    # 服务未运行
    return {
        "status": "not_running",
        "message": "Firecrawl 服务未启动，请先启动服务",
        "instructions": {
            "step1": f"cd /tmp/firecrawl",
            "step2": "sudo docker compose up -d",
            "step3": "等待约 10 秒后重试",
            "or": "运行 /home/aircas/AI/AI Studio/firecrawl-start.sh"
        }
    }