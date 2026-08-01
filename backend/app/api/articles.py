"""
文章 CRUD API

提供文章的增删改查和全文搜索功能
"""
import logging
from datetime import datetime, date
from typing import Optional, List
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
from sqlalchemy import or_, func, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.article import (
    Article, Category, ScrapeSource,
    Keyword, ArticleKeyword, ArticleLink
)
from app.services.scraper import ScrapedResult
from app.services.scraper import extract_keywords_locally, summarize_locally
from app.services import kg_sync

logger = logging.getLogger("ai-studio")

router = APIRouter(prefix="/api/articles", tags=["文章管理"])


# ============ Pydantic Schemas ============

class ArticleBase:
    """文章基础字段"""

    @classmethod
    def from_orm_with_keywords(cls, article: Article) -> dict:
        """从 ORM 对象转换为字典，包含关键词和来源名称"""
        keywords = [ak.keyword.name for ak in article.keywords if ak.keyword]
        # 获取来源名称
        source_name = None
        if article.source:
            source_name = article.source.name
        # 获取分类名称
        category_name = None
        if article.category:
            category_name = article.category.name
        return {
            "id": article.id,
            "url": article.url,
            "title": article.title,
            "content": article.content,
            "html": article.html,
            "word_count": article.word_count,
            "author": article.author,
            "summary": article.summary,
            "style": article.style,
            "content_hash": article.content_hash,
            "source_id": article.source_id,
            "source_name": source_name,
            "source_type": article.source_type,  # 信源类型
            "category_id": article.category_id,
            "category_name": category_name,
            "published_at": article.published_at.isoformat() if article.published_at else None,
            "scraped_at": article.scraped_at.isoformat() if article.scraped_at else None,
            "status": article.status,
            "error_message": article.error_message,
            "created_at": article.created_at.isoformat() if article.created_at else None,
            "updated_at": article.updated_at.isoformat() if article.updated_at else None,
            "keywords": keywords,
            # 知识图谱同步状态
            "kg_status": article.kg_status,
            "kg_processed_at": article.kg_processed_at.isoformat() if article.kg_processed_at else None,
            "kg_content_hash": article.kg_content_hash,
            "kg_error_message": article.kg_error_message,
        }


class ArticleCreate(ArticleBase):
    """创建文章请求"""

    @staticmethod
    def from_dict(data: dict) -> dict:
        """从请求数据提取有效字段"""
        return {
            "url": data.get("url", ""),
            "title": data.get("title", ""),
            "content": data.get("content", ""),
            "html": data.get("html", ""),
            "word_count": data.get("word_count", 0),
            "author": data.get("author"),
            "summary": data.get("summary", ""),
            "style": data.get("style"),
            "category_id": data.get("category_id"),
            "source_id": data.get("source_id"),
            "published_at": data.get("published_at"),
            "keywords": data.get("keywords", []),
        }


class ArticleUpdate:
    """更新文章请求"""

    @staticmethod
    def from_dict(data: dict) -> dict:
        """从请求数据提取有效字段"""
        result = {}
        if "title" in data:
            result["title"] = data["title"]
        if "content" in data:
            result["content"] = data["content"]
        if "html" in data:
            result["html"] = data["html"]
        if "author" in data:
            result["author"] = data["author"]
        if "summary" in data:
            result["summary"] = data["summary"]
        if "style" in data:
            result["style"] = data["style"]
        if "category_id" in data:
            result["category_id"] = data["category_id"]
        if "published_at" in data:
            result["published_at"] = data["published_at"]
        if "keywords" in data:
            result["keywords"] = data["keywords"]
        return result


class ArticleListResponse:
    """文章列表响应"""

    @staticmethod
    def create(items: List[Article], total: int, page: int, page_size: int) -> dict:
        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": ceil(total / page_size) if page_size > 0 else 0,
        }


class ArticleStatsResponse:
    """文章统计响应"""

    @staticmethod
    def from_query(total: int, success: int, pending: int, error: int,
                   category_stats: List[tuple]) -> dict:
        return {
            "total": total,
            "success": success,
            "pending": pending,
            "error": error,
            "by_category": [
                {"category": name, "count": count}
                for name, count in category_stats
            ],
        }


# ============ 辅助函数 ============

def _get_or_create_keywords(db: Session, keyword_names: List[str]) -> List[Keyword]:
    """获取或创建关键词"""
    if not keyword_names:
        return []

    keywords = []
    for name in keyword_names:
        if not name or not name.strip():
            continue
        name = name.strip()
        keyword = db.query(Keyword).filter(Keyword.name == name).first()
        if not keyword:
            keyword = Keyword(name=name)
            db.add(keyword)
            db.flush()
        keywords.append(keyword)
    return keywords


def _scrape_result_to_article(
    result: ScrapedResult,
    category_id: Optional[str] = None,
    source_id: Optional[str] = None
) -> Article:
    """将 ScrapedResult 转换为 Article 模型"""
    article = Article(
        url=result.url,
        title=result.title or "",
        content=result.content or "",
        html=result.html or "",
        word_count=result.word_count or 0,
        author=result.author,
        summary=result.summary or "",
        style=result.style,
        status=result.status,
        error_message=result.error_message,
        category_id=category_id,
        source_id=source_id,
    )

    # 解析日期
    if result.published_at:
        try:
            article.published_at = datetime.strptime(result.published_at, "%Y-%m-%d").date()
        except (ValueError, TypeError):
            pass

    if result.scraped_at:
        try:
            article.scraped_at = datetime.fromisoformat(result.scraped_at)
        except (ValueError, TypeError):
            pass

    # 计算内容哈希
    article.content_hash = article.calculate_content_hash()
    if article.content and not article.summary:
        article.summary = summarize_locally(article.content)

    return article


# ============ CRUD API ============

@router.get("/stats")
async def get_article_stats(db: Session = Depends(get_db)):
    """获取文章统计信息"""
    total = db.query(func.count(Article.id)).scalar() or 0
    success = db.query(func.count(Article.id)).filter(
        Article.status == "success"
    ).scalar() or 0
    pending = db.query(func.count(Article.id)).filter(
        Article.status == "pending"
    ).scalar() or 0
    error = db.query(func.count(Article.id)).filter(
        Article.status == "error"
    ).scalar() or 0

    # 按分类统计
    category_stats = db.query(
        Category.name,
        func.count(Article.id)
    ).join(
        Article, Article.category_id == Category.id
    ).group_by(Category.name).all()

    return ArticleStatsResponse.from_query(
        total, success, pending, error, category_stats
    )


@router.get("")
async def list_articles(
    q: Optional[str] = Query(None, description="搜索关键词（匹配标题、内容、摘要、关键词）"),
    category_id: Optional[str] = Query(None, description="按分类过滤 (government/business/academic)"),
    source_id: Optional[str] = Query(None, description="按来源过滤"),
    source_type: Optional[str] = Query(None, description="按信源类型过滤 (web/wechat)"),
    style: Optional[str] = Query(None, description="按文体过滤 (新闻报道/通知公告/会议纪要等)"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    start_date: Optional[str] = Query(None, description="开始日期 (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="结束日期 (YYYY-MM-DD)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取文章列表（支持分页和过滤，含标题/内容/摘要/关键词模糊搜索）"""
    query = db.query(Article)

    # 应用过滤器
    if q:
        # 模糊匹配：标题、内容、摘要、关键词
        keyword_pattern = f"%{q}%"
        query = query.outerjoin(
            ArticleKeyword, Article.id == ArticleKeyword.article_id
        ).outerjoin(
            Keyword, ArticleKeyword.keyword_id == Keyword.id
        ).filter(
            or_(
                Article.title.ilike(keyword_pattern),
                Article.content.ilike(keyword_pattern),
                Article.summary.ilike(keyword_pattern),
                Keyword.name.ilike(keyword_pattern)
            )
        )
    if category_id:
        query = query.filter(Article.category_id == category_id)
    if source_id:
        query = query.filter(Article.source_id == source_id)
    if source_type:
        query = query.filter(Article.source_type == source_type)
    if style:
        # 文体筛选，使用模糊匹配
        query = query.filter(Article.style.ilike(f"%{style}%"))
    if status:
        query = query.filter(Article.status == status)
    if start_date:
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            query = query.filter(Article.published_at >= start)
        except ValueError:
            pass
    if end_date:
        try:
            end = datetime.strptime(end_date, "%Y-%m-%d").date()
            query = query.filter(Article.published_at <= end)
        except ValueError:
            pass

    # 获取总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    articles = query.order_by(
        Article.published_at.desc().nullslast(),
        Article.scraped_at.desc()
    ).offset(offset).limit(page_size).all()

    # 转换为响应格式
    items = [
        ArticleBase.from_orm_with_keywords(a)
        for a in articles
    ]

    return ArticleListResponse.create(items, total, page, page_size)


@router.get("/{article_id}")
async def get_article(article_id: str, db: Session = Depends(get_db)):
    """获取单个文章"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    return ArticleBase.from_orm_with_keywords(article)


@router.post("")
async def create_article(
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """创建文章"""
    data = ArticleCreate.from_dict(request)

    if not data.get("url"):
        raise HTTPException(status_code=400, detail="URL 不能为空")

    # 检查 URL 是否已存在
    existing = db.query(Article).filter(Article.url == data["url"]).first()
    if existing:
        raise HTTPException(status_code=409, detail="文章 URL 已存在")

    # 解析日期
    published_at = None
    if data.get("published_at"):
        try:
            published_at = datetime.strptime(data["published_at"], "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    # 计算内容哈希
    content = data.get("content", "")
    content_hash = None
    if content:
        import hashlib
        content_hash = hashlib.sha256(content.encode()).hexdigest()

    # 创建文章
    article = Article(
        url=data["url"],
        title=data.get("title", ""),
        content=content,
        html=data.get("html", ""),
        word_count=data.get("word_count", len(content.replace(" ", "").replace("\n", ""))),
        author=data.get("author"),
        summary=data.get("summary", ""),
        style=data.get("style"),
        content_hash=content_hash,
        category_id=data.get("category_id"),
        source_id=data.get("source_id"),
        published_at=published_at,
        status="success",
    )

    keyword_names = data.get("keywords") or extract_keywords_locally(
        article.title,
        article.content,
    )

    # 处理关键词
    if keyword_names:
        keywords = _get_or_create_keywords(db, keyword_names)
        for kw in keywords:
            article.keywords.append(ArticleKeyword(keyword_id=kw.id))

    db.add(article)
    db.commit()
    db.refresh(article)

    logger.info(f"创建文章: id={article.id}, title={article.title[:50]}")

    # 同步 KG(metadata + 后台抽实体)
    await kg_sync.on_article_created(article, background_tasks)

    return ArticleBase.from_orm_with_keywords(article)


@router.put("/{article_id}")
async def update_article(
    article_id: str,
    request: dict,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """更新文章"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    update_data = ArticleUpdate.from_dict(request)

    # 更新基本字段
    for field in ["title", "content", "html", "author", "summary", "style", "category_id"]:
        if field in update_data:
            setattr(article, field, update_data[field])

    # 更新日期
    if "published_at" in update_data:
        if update_data["published_at"]:
            try:
                article.published_at = datetime.strptime(
                    update_data["published_at"], "%Y-%m-%d"
                ).date()
            except ValueError:
                raise HTTPException(status_code=400, detail="日期格式错误")
        else:
            article.published_at = None

    # 更新关键词
    if "keywords" in update_data:
        # 清除旧关键词
        db.query(ArticleKeyword).filter(
            ArticleKeyword.article_id == article_id
        ).delete()

        # 添加新关键词
        if update_data["keywords"]:
            keywords = _get_or_create_keywords(db, update_data["keywords"])
            for kw in keywords:
                article.keywords.append(ArticleKeyword(keyword_id=kw.id))

    # 更新内容后重新计算哈希和字数
    if "content" in update_data:
        article.content_hash = article.calculate_content_hash()
        article.word_count = len(
            article.content.replace(" ", "").replace("\n", "")
        )

    db.commit()
    db.refresh(article)

    logger.info(f"更新文章: id={article.id}")

    # 同步 KG(metadata;若内容变了,kg_status 自动变 pending)
    await kg_sync.on_article_updated(article, background_tasks)

    return ArticleBase.from_orm_with_keywords(article)


@router.delete("/{article_id}")
async def delete_article(article_id: str, db: Session = Depends(get_db)):
    """删除文章"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 先删 KG(SQLite 删除后找不到 id)
    try:
        await kg_sync.on_article_deleted(article_id)
    except Exception as e:
        logger.warning(f"删除文章 {article_id} 的 KG 数据失败(继续删 SQLite): {e}")

    db.delete(article)
    db.commit()

    logger.info(f"删除文章: id={article_id}")

    return {"message": "文章已删除"}


@router.post("/batch-delete")
async def batch_delete_articles(
    ids: List[str] = Body(..., embed=True, description="文章ID列表"),
    db: Session = Depends(get_db)
):
    """批量删除文章"""
    if not ids:
        raise HTTPException(status_code=400, detail="ID列表不能为空")

    deleted = 0
    errors = []

    for article_id in ids:
        try:
            article = db.query(Article).filter(Article.id == article_id).first()
            if article:
                # 先删 KG
                try:
                    await kg_sync.on_article_deleted(article_id)
                except Exception as e:
                    logger.warning(f"批量删除 {article_id} 的 KG 数据失败(继续): {e}")
                # 再删除关联的关键词
                db.query(ArticleKeyword).filter(
                    ArticleKeyword.article_id == article_id
                ).delete()
                # 再删除关联的链接
                db.query(ArticleLink).filter(
                    ArticleLink.source_article_id == article_id
                ).delete()
                db.delete(article)
                deleted += 1
            else:
                errors.append({"id": article_id, "error": "文章不存在"})
        except Exception as e:
            errors.append({"id": article_id, "error": str(e)})
            db.rollback()

    db.commit()

    logger.info(f"批量删除完成: 成功删除={deleted}, 失败={len(errors)}")

    return {"deleted": deleted, "errors": errors}


@router.post("/scrape-result")
async def save_scrape_result(
    result: ScrapedResult,
    background_tasks: BackgroundTasks,
    category_id: Optional[str] = Query(None, description="分类 ID"),
    source_id: Optional[str] = Query(None, description="来源 ID"),
    db: Session = Depends(get_db)
):
    """保存爬取结果到数据库"""
    # 检查是否已存在
    existing = db.query(Article).filter(Article.url == result.url).first()

    if existing:
        # 更新已存在的文章
        existing.title = result.title or existing.title
        existing.content = result.content or existing.content
        existing.html = result.html or existing.html
        existing.word_count = result.word_count or existing.word_count
        existing.author = result.author or existing.author
        existing.summary = result.summary or existing.summary
        existing.style = result.style or existing.style
        existing.status = result.status
        existing.error_message = result.error_message

        if result.published_at:
            try:
                existing.published_at = datetime.strptime(
                    result.published_at, "%Y-%m-%d"
                ).date()
            except (ValueError, TypeError):
                pass

        existing.content_hash = existing.calculate_content_hash()

        keyword_names = result.keywords or extract_keywords_locally(
            existing.title or result.title or "",
            existing.content or result.content or "",
        )

        # 更新关键词
        if keyword_names:
            db.query(ArticleKeyword).filter(
                ArticleKeyword.article_id == existing.id
            ).delete()

            keywords = _get_or_create_keywords(db, keyword_names)
            for kw in keywords:
                existing.keywords.append(ArticleKeyword(keyword_id=kw.id))

        db.commit()
        db.refresh(existing)
        logger.info(f"更新爬取结果: id={existing.id}, url={existing.url[:50]}")

        # 同步 KG(metadata)
        try:
            await kg_sync.on_article_updated(existing, background_tasks)
        except Exception as e:
            logger.warning(f"更新爬取结果后 KG 同步失败(继续): {e}")

        return {"id": existing.id, "action": "updated"}

    # 创建新文章
    article = _scrape_result_to_article(result, category_id, source_id)

    # 保存链接
    if result.links:
        for link_url in result.links:
            article.links.append(ArticleLink(target_url=link_url))

    keyword_names = result.keywords or extract_keywords_locally(article.title, article.content)

    # 保存关键词
    if keyword_names:
        keywords = _get_or_create_keywords(db, keyword_names)
        for kw in keywords:
            article.keywords.append(ArticleKeyword(keyword_id=kw.id))

    db.add(article)
    db.commit()
    db.refresh(article)

    logger.info(f"保存爬取结果: id={article.id}, url={article.url[:50]}")

    # 同步 KG(metadata + 后台抽实体)
    try:
        await kg_sync.on_article_created(article, background_tasks)
    except Exception as e:
        logger.warning(f"保存爬取结果后 KG 同步失败(继续): {e}")

    return {"id": article.id, "action": "created"}


@router.post("/batch")
async def batch_save_articles(
    results: List[ScrapedResult],
    background_tasks: BackgroundTasks,
    category_ids: Optional[List[str]] = Query(None, description="对应每个结果的分类 ID"),
    source_ids: Optional[List[str]] = Query(None, description="对应每个结果的来源 ID"),
    db: Session = Depends(get_db)
):
    """批量保存爬取结果"""
    created = 0
    updated = 0
    errors = []

    for i, result in enumerate(results):
        category_id = category_ids[i] if category_ids and i < len(category_ids) else None
        source_id = source_ids[i] if source_ids and i < len(source_ids) else None

        try:
            existing = db.query(Article).filter(Article.url == result.url).first()

            if existing:
                existing.title = result.title or existing.title
                existing.content = result.content or existing.content
                existing.html = result.html or existing.html
                existing.word_count = result.word_count or existing.word_count
                existing.author = result.author or existing.author
                existing.summary = result.summary or existing.summary
                existing.style = result.style or existing.style
                existing.status = result.status
                existing.content_hash = existing.calculate_content_hash()
                keyword_names = result.keywords or extract_keywords_locally(existing.title, existing.content)
                if keyword_names:
                    db.query(ArticleKeyword).filter(
                        ArticleKeyword.article_id == existing.id
                    ).delete()
                    keywords = _get_or_create_keywords(db, keyword_names)
                    for kw in keywords:
                        existing.keywords.append(ArticleKeyword(keyword_id=kw.id))
                updated += 1
            else:
                article = _scrape_result_to_article(result, category_id, source_id)
                keyword_names = result.keywords or extract_keywords_locally(article.title, article.content)
                if keyword_names:
                    keywords = _get_or_create_keywords(db, keyword_names)
                    for kw in keywords:
                        article.keywords.append(ArticleKeyword(keyword_id=kw.id))
                db.add(article)
                created += 1

        except Exception as e:
            errors.append({"url": result.url, "error": str(e)})

    db.commit()

    # 批量同步 KG(对刚创建/更新的文章)
    try:
        # 找刚才处理过的文章(按 url 列表)
        url_list = [r.url for r in results]
        if url_list:
            processed = db.query(Article).filter(Article.url.in_(url_list)).all()
            for art in processed:
                if art.status == "success":
                    try:
                        await kg_sync.on_article_created(art, background_tasks)
                    except Exception as e:
                        logger.warning(f"批量保存 {art.id} 的 KG 同步失败(继续): {e}")
    except Exception as e:
        logger.warning(f"批量保存 KG 同步阶段失败(继续): {e}")

    logger.info(f"批量保存完成: 创建={created}, 更新={updated}, 错误={len(errors)}")

    return {
        "created": created,
        "updated": updated,
        "errors": errors,
    }


@router.post("/search")
async def search_articles(
    q: str = Query(..., min_length=1, description="搜索关键词（全文搜索 + 关键词匹配）"),
    category_id: Optional[str] = Query(None, description="按分类过滤 (government/business/academic)"),
    source_id: Optional[str] = Query(None, description="按来源过滤"),
    source_type: Optional[str] = Query(None, description="按信源类型过滤 (web/wechat)"),
    style: Optional[str] = Query(None, description="按文体过滤 (新闻报道/通知公告/会议纪要等)"),
    status: str = Query("success", description="按状态过滤"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    db: Session = Depends(get_db)
):
    """全文搜索文章（标题/内容/摘要 + 关键词模糊匹配）"""
    # 使用 PostgreSQL 全文搜索 + 关键词匹配
    search_query = q.replace("'", "''")
    keyword_pattern = f"%{search_query}%"

    # 构建基本查询
    query = db.query(Article)

    # 添加关键词 JOIN
    query = query.outerjoin(
        ArticleKeyword, Article.id == ArticleKeyword.article_id
    ).outerjoin(
        Keyword, ArticleKeyword.keyword_id == Keyword.id
    )

    # 添加过滤条件
    if category_id:
        query = query.filter(Article.category_id == category_id)
    if source_id:
        query = query.filter(Article.source_id == source_id)
    if source_type:
        query = query.filter(Article.source_type == source_type)
    if style:
        # 文体筛选，使用模糊匹配
        query = query.filter(Article.style.ilike(f"%{style}%"))
    if status:
        query = query.filter(Article.status == status)

    # 执行全文搜索
    fts_query = text("""
        SELECT id FROM articles
        WHERE search_vector @@ plainto_tsquery('chinese', :query)
        ORDER BY ts_rank(search_vector, plainto_tsquery('chinese', :query)) DESC
    """)

    result = db.execute(fts_query, {"query": search_query})
    article_ids = [row[0] for row in result.fetchall()]

    # 添加关键词模糊匹配（独立查询）
    keyword_query = text("""
        SELECT DISTINCT ak.article_id FROM article_keywords ak
        JOIN keywords k ON ak.keyword_id = k.id
        WHERE k.name ILIKE :pattern
    """)
    keyword_result = db.execute(keyword_query, {"pattern": keyword_pattern})
    keyword_article_ids = [row[0] for row in keyword_result.fetchall()]

    # 合并全文搜索和关键词搜索结果
    all_article_ids = list(set(article_ids + keyword_article_ids))

    if not all_article_ids:
        return ArticleListResponse.create([], 0, page, page_size)

    # 按搜索排名排序（全文搜索结果优先）
    id_order = {aid: i for i, aid in enumerate(article_ids)}
    keyword_articles = [aid for aid in all_article_ids if aid not in id_order]
    sorted_ids = article_ids + keyword_articles

    # 按排序结果筛选
    query = query.filter(Article.id.in_(all_article_ids))

    # 获取总数
    total = query.distinct().count()

    # 分页
    offset = (page - 1) * page_size
    articles = query.offset(offset).limit(page_size).all()

    # 按搜索排名重新排序
    sorted_articles = sorted(articles, key=lambda a: sorted_ids.index(a.id) if a.id in sorted_ids else 999)

    items = [ArticleBase.from_orm_with_keywords(a) for a in sorted_articles]

    return ArticleListResponse.create(items, total, page, page_size)


# ============ 分类和来源管理 ============

@router.get("/styles/", response_model=List[dict])
async def list_styles(db: Session = Depends(get_db)):
    """获取所有文体类型（按使用频率排序）"""
    styles = db.query(
        Article.style,
        func.count(Article.id).label("count")
    ).filter(
        Article.style.isnot(None),
        Article.style != ""
    ).group_by(
        Article.style
    ).order_by(
        func.count(Article.id).desc()
    ).all()

    return [
        {"name": name, "count": count}
        for name, count in styles
    ]


@router.get("/categories/", response_model=List[dict])
async def list_categories(db: Session = Depends(get_db)):
    """获取所有分类"""
    categories = db.query(Category).order_by(Category.name).all()
    return [c.to_dict() for c in categories]


@router.get("/sources/", response_model=List[dict])
async def list_sources(
    category_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取所有爬取源"""
    query = db.query(ScrapeSource)
    if category_id:
        query = query.filter(ScrapeSource.category_id == category_id)
    sources = query.order_by(ScrapeSource.name).all()
    return [s.to_dict() for s in sources]


@router.get("/keywords/", response_model=List[dict])
async def list_keywords(
    limit: int = Query(50, ge=1, le=500, description="最大返回数量"),
    db: Session = Depends(get_db)
):
    """获取所有关键词（按使用频率排序）"""
    keywords = db.query(
        Keyword,
        func.count(ArticleKeyword.article_id).label("usage_count")
    ).join(
        ArticleKeyword
    ).group_by(
        Keyword.id
    ).order_by(
        func.count(ArticleKeyword.article_id).desc()
    ).limit(limit).all()

    return [
        {"id": kw.id, "name": kw.name, "usage_count": count}
        for kw, count in keywords
    ]


@router.get("/url/{url}")
async def get_article_by_url(url: str, db: Session = Depends(get_db)):
    """根据 URL 获取文章"""
    article = db.query(Article).filter(Article.url == url).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")
    return ArticleBase.from_orm_with_keywords(article)


@router.get("/check-url/{url}")
async def check_url_exists(url: str, db: Session = Depends(get_db)):
    """检查 URL 是否已存在"""
    article = db.query(Article).filter(Article.url == url).first()
    return {"exists": article is not None, "article_id": article.id if article else None}
