from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
import json
import os
from pathlib import Path

router = APIRouter(prefix="/settings", tags=["设置"])


# ============ 请求/响应模型 ============

# ============ 分类管理 ============

class CategoryRequest(BaseModel):
    """分类请求"""
    name: str                          # 分类名称
    id: Optional[str] = None           # 分类ID（更新时使用）
    color: Optional[str] = None        # 颜色（可选）


class CategoryResponse(BaseModel):
    """分类响应"""
    id: str
    name: str
    color: str
    description: str = ""
    folder_name: str                   # 对应的文件夹名称
    source_count: int = 0              # 该分类下的来源数量
    created_at: str
    updated_at: str


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

# 内容存储根目录
CONTENT_ROOT = Path(__file__).parent.parent.parent / "data" / "content"


def _sanitize_folder_name(name: str) -> str:
    """将分类名称转换为安全的文件夹名称"""
    # 移除特殊字符，只保留中文、英文、数字和空格
    import re
    safe = re.sub(r'[^\w\s一-鿿-]', '', name)
    # 空格替换为下划线
    safe = safe.replace(' ', '_')
    return safe if safe else "untitled"


def _get_default_categories() -> List[dict]:
    """获取默认分类列表"""
    return [
        {"id": "government", "name": "党政类", "color": "#EF4444", "description": "政府机关、党政部门相关网站"},
        {"id": "business", "name": "商务类", "color": "#3B82F6", "description": "商业企业、财经商务相关网站"},
        {"id": "academic", "name": "学术类", "color": "#10B981", "description": "学术研究、教育机构相关网站"},
    ]


class SettingsStore:
    def __init__(self):
        self.settings = {
            "theme": "dark",
            "primary_color": "indigo",
            "firecrawl": FirecrawlConfig().model_dump(),
        }
        self.scrape_sources = {}
        self.categories = {}        # 分类数据
        self._source_counter = 0
        self._category_counter = 0
        self._load_from_file()
        # 从数据库恢复用户配置的爬取源（文件可能被覆盖，数据库是权威持久化来源）
        self._recover_from_database()
        # 确保默认分类存在
        self._ensure_default_categories()

    def _ensure_data_dir(self):
        """确保数据目录存在"""
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)

    def _ensure_content_dir(self):
        """确保内容存储目录存在"""
        CONTENT_ROOT.mkdir(parents=True, exist_ok=True)

    def _ensure_category_folder(self, category_id: str, folder_name: str):
        """确保分类对应的文件夹存在"""
        self._ensure_content_dir()
        category_dir = CONTENT_ROOT / folder_name
        if not category_dir.exists():
            category_dir.mkdir(parents=True, exist_ok=True)
            print(f"创建分类文件夹: {category_dir}")
        return category_dir

    def _ensure_default_categories(self):
        """确保默认分类存在，初始化时创建"""
        if not self.categories:
            default_cats = _get_default_categories()
            now = datetime.now().isoformat()
            for cat in default_cats:
                self.categories[cat["id"]] = {
                    **cat,
                    "folder_name": _sanitize_folder_name(cat["name"]),
                    "created_at": now,
                    "updated_at": now,
                }
                # 创建对应的文件夹
                self._ensure_category_folder(cat["id"], _sanitize_folder_name(cat["name"]))
            self._save_to_file()

    def _load_from_file(self):
        """从文件加载配置"""
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.settings = data.get("settings", self.settings)
                    self.scrape_sources = data.get("scrape_sources", {})
                    self.categories = data.get("categories", {})

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
                    # 更新分类计数器
                    for cat_id in self.categories.keys():
                        try:
                            parts = cat_id.split("_")
                            if len(parts) >= 2:
                                counter = int(parts[1])
                                if counter > self._category_counter:
                                    self._category_counter = counter
                        except:
                            pass
                    # 确保 firecrawl 配置存在
                    if "firecrawl" not in self.settings:
                        self.settings["firecrawl"] = FirecrawlConfig().model_dump()
            except Exception as e:
                print(f"[设置] 加载配置文件失败: {e}")

    def _save_to_file(self):
        """保存配置到文件"""
        self._ensure_data_dir()
        try:
            data = {
                "settings": self.settings,
                "scrape_sources": self.scrape_sources,
                "categories": self.categories,
            }
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def _sync_to_database(self):
        """同步关系型配置；数据库暂不可用时保留文件配置并记录错误。"""
        try:
            from app.core.database import sync_settings_to_database
            sync_settings_to_database(self.categories, self.scrape_sources)
        except Exception as e:
            print(f"同步配置到数据库失败: {e}")

    def _recover_from_database(self):
        """从数据库恢复用户配置的爬取源。

        数据库是权威持久化来源，持久化了用户界面添加的爬取源。当 settings.json
        因被覆盖等原因缺失用户数据时，启动时将数据库中的爬取源合并进来并写回文件，
        保证重启后界面仍能显示用户配置的完整的爬取网站列表。
        """
        try:
            from app.core.database import load_scrape_sources_from_database
            db_sources = load_scrape_sources_from_database()
            if not db_sources:
                return
            # 合并：数据库中有而文件缺失的来源，补入内存
            merged = False
            for name, src in db_sources.items():
                exists = any(
                    s.get("name") == name for s in self.scrape_sources.values()
                )
                if not exists:
                    self._source_counter += 1
                    src["id"] = f"src_{self._source_counter}_{int(datetime.now().timestamp() * 1000) % 1000000}"
                    self.scrape_sources[src["id"]] = src
                    merged = True
            if merged:
                self._save_to_file()
                print(f"[设置] 已从数据库恢复 {sum(1 for s in self.scrape_sources.values() if s.get('name') in db_sources)} 个爬取源")
        except Exception as e:
            print(f"[设置] 从数据库恢复爬取源失败: {e}")

    def _get_category_source_count(self, category_id: str) -> int:
        """获取分类下的来源数量"""
        return sum(1 for s in self.scrape_sources.values() if s.get("category") == category_id)

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

        # 构建分类列表（带来源数量）
        categories = []
        for cat_id, cat in self.categories.items():
            categories.append(CategoryResponse(
                id=cat["id"],
                name=cat["name"],
                color=cat.get("color", "#6B7280"),
                description=cat.get("description", ""),
                folder_name=cat.get("folder_name", ""),
                source_count=self._get_category_source_count(cat_id),
                created_at=cat["created_at"],
                updated_at=cat["updated_at"],
            ))

        return {
            **self.settings,
            "scrape_sources": sorted(sources, key=lambda x: x.created_at, reverse=True),
            "categories": categories,
            "firecrawl": self.settings.get("firecrawl", FirecrawlConfig().model_dump()),
        }

    # ============ 分类管理方法 ============

    def get_categories(self) -> List[CategoryResponse]:
        """获取所有分类"""
        categories = []
        for cat_id, cat in self.categories.items():
            categories.append(CategoryResponse(
                id=cat["id"],
                name=cat["name"],
                color=cat.get("color", "#6B7280"),
                description=cat.get("description", ""),
                folder_name=cat.get("folder_name", ""),
                source_count=self._get_category_source_count(cat_id),
                created_at=cat["created_at"],
                updated_at=cat["updated_at"],
            ))
        return sorted(categories, key=lambda x: x.created_at)

    def add_category(self, data: dict) -> CategoryResponse:
        """添加新分类"""
        self._category_counter += 1
        now = datetime.now().isoformat()
        name = data["name"]
        folder_name = _sanitize_folder_name(name)

        # 生成唯一 ID
        category_id = f"cat_{self._category_counter}_{int(datetime.now().timestamp())}"

        new_category = {
            "id": category_id,
            "name": name,
            "color": data.get("color", "#6B7280"),
            "description": data.get("description", ""),
            "folder_name": folder_name,
            "created_at": now,
            "updated_at": now,
        }
        self.categories[category_id] = new_category
        self._save_to_file()
        self._sync_to_database()

        # 创建对应的文件夹
        self._ensure_category_folder(category_id, folder_name)

        return CategoryResponse(**new_category, source_count=0)

    def update_category(self, category_id: str, data: dict) -> Optional[CategoryResponse]:
        """更新分类"""
        if category_id not in self.categories:
            return None

        category = self.categories[category_id]
        old_folder_name = category.get("folder_name", "")

        # 更新字段
        if "name" in data:
            category["name"] = data["name"]
            category["folder_name"] = _sanitize_folder_name(data["name"])
        if "color" in data:
            category["color"] = data["color"]
        if "description" in data:
            category["description"] = data["description"]

        category["updated_at"] = datetime.now().isoformat()
        self._save_to_file()
        self._sync_to_database()

        # 如果文件夹名称改变，尝试重命名
        new_folder_name = category.get("folder_name", "")
        if old_folder_name and new_folder_name and old_folder_name != new_folder_name:
            old_path = CONTENT_ROOT / old_folder_name
            new_path = CONTENT_ROOT / new_folder_name
            if old_path.exists() and not new_path.exists():
                old_path.rename(new_path)
                print(f"重命名分类文件夹: {old_folder_name} -> {new_folder_name}")

        return CategoryResponse(
            **category,
            source_count=self._get_category_source_count(category_id),
        )

    def delete_category(self, category_id: str) -> bool:
        """删除分类"""
        if category_id not in self.categories:
            return False

        # 检查是否有来源使用该分类
        source_count = self._get_category_source_count(category_id)
        if source_count > 0:
            print(f"无法删除分类 {category_id}，仍有 {source_count} 个来源在使用")
            return False

        category = self.categories[category_id]
        folder_name = category.get("folder_name", "")

        # 删除分类数据
        del self.categories[category_id]
        self._save_to_file()

        # 注意：不自动删除文件夹，保留历史数据
        print(f"已删除分类: {category_id}")

        return True

    def get_category_path(self, category_id: str) -> Optional[Path]:
        """获取分类对应的文件夹路径"""
        if category_id not in self.categories:
            return None
        folder_name = self.categories[category_id].get("folder_name", "")
        if folder_name:
            return CONTENT_ROOT / folder_name
        return CONTENT_ROOT / _sanitize_folder_name(self.categories[category_id]["name"])

    def list_content_files(self, category_id: Optional[str] = None) -> List[dict]:
        """列出分类下的内容文件"""
        self._ensure_content_dir()

        result = []
        if category_id:
            cat_path = self.get_category_path(category_id)
            if cat_path and cat_path.exists():
                paths = [cat_path]
            else:
                return []
        else:
            paths = [CONTENT_ROOT]

        for base_path in paths:
            if not base_path.exists():
                continue
            for f in base_path.iterdir():
                if f.is_file() and f.suffix in ['.md', '.txt', '.html']:
                    stat = f.stat()
                    result.append({
                        "filename": f.name,
                        "path": str(f.relative_to(CONTENT_ROOT)),
                        "size": stat.st_size,
                        "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })

        return sorted(result, key=lambda x: x["modified_at"], reverse=True)

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
        self._sync_to_database()
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
        self._sync_to_database()
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
        self._sync_to_database()
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


# ============ 分类管理 API ============

@router.get("/categories", response_model=List[CategoryResponse])
async def list_categories():
    """获取所有分类"""
    return settings_store.get_categories()


@router.post("/categories", response_model=CategoryResponse)
async def add_category(request: CategoryRequest):
    """添加新分类"""
    if not request.name.strip():
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="分类名称不能为空")

    # 检查名称是否重复
    existing = [c for c in settings_store.categories.values() if c["name"] == request.name.strip()]
    if existing:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="分类名称已存在")

    return settings_store.add_category({
        "name": request.name.strip(),
        "color": request.color,
        "description": "",
    })


@router.put("/categories/{category_id}", response_model=CategoryResponse)
async def update_category(category_id: str, request: CategoryRequest):
    """更新分类"""
    # 检查名称是否重复（排除自己）
    if request.name and request.name.strip():
        existing = [c for c in settings_store.categories.values()
                    if c["name"] == request.name.strip() and c["id"] != category_id]
        if existing:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail="分类名称已存在")

    result = settings_store.update_category(category_id, {
        "name": request.name,
        "color": request.color,
    })
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="分类不存在")
    return result


@router.delete("/categories/{category_id}")
async def delete_category(category_id: str):
    """删除分类"""
    # 不允许删除默认分类
    default_ids = ["government", "business", "academic"]
    if category_id in default_ids:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="默认分类不能删除")

    # 检查是否有来源使用该分类
    source_count = settings_store._get_category_source_count(category_id)
    if source_count > 0:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"该分类下有 {source_count} 个来源，无法删除")

    if not settings_store.delete_category(category_id):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"message": "分类已删除"}


# ============ 内容文件管理 API ============

@router.get("/content")
async def list_content_files(category_id: Optional[str] = None):
    """列出分类下的内容文件"""
    return settings_store.list_content_files(category_id)


class SaveContentRequest(BaseModel):
    """保存内容请求"""
    filename: str
    category_id: str
    content: str


@router.post("/content")
async def save_content_file(request: SaveContentRequest):
    """保存内容文件到服务器"""
    from fastapi import HTTPException

    # 获取分类路径
    cat_path = settings_store.get_category_path(request.category_id)
    if cat_path is None:
        # 如果没有指定分类，使用根目录下的 uncategorized 文件夹
        settings_store._ensure_content_dir()
        cat_path = CONTENT_ROOT / "uncategorized"
        cat_path.mkdir(exist_ok=True)

    # 清理文件名
    safe_filename = request.filename.replace("/", "_").replace("\\", "_").replace("..", "_")
    file_path = cat_path / safe_filename

    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.content)
        return {
            "message": "文件已保存",
            "path": str(file_path.relative_to(CONTENT_ROOT)),
            "size": file_path.stat().st_size,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存失败: {str(e)}")


@router.get("/content/download/{category_id}/{filename}")
async def download_content_file(category_id: str, filename: str):
    """下载内容文件"""
    from fastapi import HTTPException

    cat_path = settings_store.get_category_path(category_id)
    if cat_path is None:
        raise HTTPException(status_code=404, detail="分类不存在")

    file_path = cat_path / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="文件不存在")

    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="text/markdown" if filename.endswith(".md") else "text/plain",
    )


@router.get("/content/path")
async def get_content_root_path():
    """获取内容存储根目录路径"""
    settings_store._ensure_content_dir()
    return {
        "root": str(CONTENT_ROOT),
        "exists": CONTENT_ROOT.exists(),
    }


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
