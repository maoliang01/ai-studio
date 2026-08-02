"""
知识图谱 API

提供知识图谱的构建、查询和管理功能
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any, Literal
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.core.database import get_db
from app.models.article import Article
from app.services.kg import Neo4jService, EntityExtractor, EmbeddingService
from app.services.kg.graph import EntityNode, Relationship
from app.services.kg.embedding import VectorStore
from app.services.kg.qa import answer_question
from app.services.kg.mining import find_relation_evidence
from app.services import kg_sync

logger = logging.getLogger("ai-studio")

router = APIRouter(prefix="/api/kg", tags=["知识图谱"])


# ============ 依赖项 ============

def get_neo4j_service() -> Neo4jService:
    """获取 Neo4j 服务实例"""
    return Neo4jService()


def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务实例"""
    return EmbeddingService()


def get_causal_article_records(db: Session) -> List[Dict[str, Any]]:
    """Load the bounded historical corpus used for review-only causal mining."""
    articles = (
        db.query(Article)
        .filter(Article.status == "success")
        .order_by(Article.scraped_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": str(article.id),
            "content": article.content or "",
            "summary": article.summary or "",
        }
        for article in articles
    ]


# ============ 健康检查 ============

@router.get("/health")
async def check_kg_health():
    """检查知识图谱服务状态"""
    try:
        neo4j = Neo4jService()
        is_connected = await neo4j.verify_connection()

        return {
            "status": "healthy" if is_connected else "unhealthy",
            "neo4j": {
                "connected": is_connected,
                "uri": neo4j.uri
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }


@router.post("/init")
async def init_knowledge_graph():
    """初始化知识图谱（设置约束和索引）"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        await neo4j.init_schema()
        await neo4j.close()

        return {"status": "success", "message": "知识图谱初始化完成"}
    except Exception as e:
        logger.error(f"初始化知识图谱失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 图谱统计 ============

@router.get("/stats")
async def get_graph_stats():
    """获取图谱统计信息(含与 SQLite 的对账)"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        stats = await neo4j.get_graph_stats()
        await neo4j.close()

        # 加上 SQLite 计数与漂移检测(以文档管理为最终口径)
        from app.core.database import get_session_local
        SessionLocal = get_session_local()
        session = SessionLocal()
        try:
            db_count = session.query(Article).filter(Article.status == "success").count()
        finally:
            session.close()

        stats["articles_in_db"] = db_count
        kg_articles = stats.get("articles", 0)
        stats["orphan_entities"] = stats.get("orphan_entities", 0)
        stats["drift_detected"] = kg_articles != db_count or stats["orphan_entities"] > 0

        return {
            "status": "success",
            "stats": stats
        }
    except Exception as e:
        logger.error(f"获取图谱统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 单篇文章处理 ============

@router.post("/process/{article_id}")
async def process_article(
    article_id: str,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    处理单篇文章，提取实体并构建图谱

    Args:
        article_id: 文章 ID
    """
    # 获取文章
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    try:
        # 初始化服务
        neo4j = Neo4jService()
        extractor = EntityExtractor()

        await neo4j.connect()

        # 1. 创建文章节点
        await neo4j.create_article_node(
            article_id=article.id,
            title=article.title or "",
            url=article.url or "",
            summary=article.summary
        )

        # 2. 提取实体和关系
        content = article.content or article.summary or ""
        if not content:
            await neo4j.close()
            return {"status": "skipped", "message": "文章内容为空"}

        result = await extractor.extract(content)

        if result.error:
            await neo4j.close()
            raise HTTPException(status_code=500, detail=f"实体抽取失败: {result.error}")

        # 3. 去重实体
        entities = extractor.deduplicate_entities(result.entities)
        relations = result.relations

        # 4. 批量创建实体和关系
        stats = await neo4j.batch_create_entities_and_relations(
            article_id=article.id,
            entities=entities,
            relations=relations
        )

        await neo4j.close()

        return {
            "status": "success",
            "article_id": article_id,
            "entities_count": len(entities),
            "relations_count": len(relations),
            "created": stats
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"处理文章失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 批量处理 ============

@router.post("/batch-process")
async def batch_process_articles(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    批量处理文章

    Args:
        limit: 最大处理数量
    """
    try:
        # 获取待处理文章（按时间排序）
        articles = db.query(Article).filter(
            Article.status == "success"
        ).order_by(Article.scraped_at.desc()).limit(limit).all()

        if not articles:
            return {"status": "success", "message": "没有待处理文章", "processed": 0}

        neo4j = Neo4jService()
        extractor = EntityExtractor()

        await neo4j.connect()
        await neo4j.init_schema()

        results = {
            "total": len(articles),
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "errors": []
        }

        for article in articles:
            try:
                # 检查是否已处理
                existing = await neo4j.get_article_entities(article.id)
                if existing:
                    results["skipped"] += 1
                    continue

                # 创建文章节点
                await neo4j.create_article_node(
                    article_id=article.id,
                    title=article.title or "",
                    url=article.url or "",
                    summary=article.summary
                )

                # 提取实体
                content = article.content or article.summary or ""
                if not content:
                    results["skipped"] += 1
                    continue

                result = await extractor.extract(content)

                if result.error:
                    results["failed"] += 1
                    results["errors"].append({
                        "article_id": article.id,
                        "error": result.error
                    })
                    continue

                # 去重并保存
                entities = extractor.deduplicate_entities(result.entities)
                relations = result.relations

                await neo4j.batch_create_entities_and_relations(
                    article_id=article.id,
                    entities=entities,
                    relations=relations
                )

                results["success"] += 1

                # 添加小延迟避免 API 限流
                await asyncio.sleep(0.5)

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "article_id": article.id,
                    "error": str(e)
                })
                logger.error(f"处理文章 {article.id} 失败: {e}")

        await neo4j.close()

        return {
            "status": "success",
            "results": results
        }

    except Exception as e:
        logger.error(f"批量处理失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 查询功能 ============

@router.get("/search")
async def search_entities(
    query: str = Query(default="", description="搜索关键词"),
    entity_type: Optional[str] = Query(default=None, description="实体类型"),
    limit: int = Query(default=50, ge=1, le=200)
):
    """
    搜索实体

    Args:
        query: 搜索关键词
        entity_type: 实体类型过滤
        limit: 返回数量限制
    """
    try:
        neo4j = Neo4jService()
        await neo4j.connect()

        entities = await neo4j.search_entities(
            query=query if query else None,
            entity_type=entity_type,
            limit=limit
        )

        await neo4j.close()

        return {
            "status": "success",
            "count": len(entities),
            "entities": entities
        }

    except Exception as e:
        logger.error(f"搜索实体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/article/{article_id}")
async def get_article_kg(article_id: str):
    """获取文章的图谱数据"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()

        # 获取文章信息
        article_neo4j = await neo4j.get_article_entities(article_id)

        await neo4j.close()

        return {
            "status": "success",
            "article_id": article_id,
            "entities": article_neo4j
        }

    except Exception as e:
        logger.error(f"获取文章图谱失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity/{entity_name}")
async def get_entity_details(
    entity_name: str,
    depth: int = Query(default=1, ge=1, le=3)
):
    """
    获取实体详情和邻居

    Args:
        entity_name: 实体名称
        depth: 关系深度
    """
    try:
        neo4j = Neo4jService()
        await neo4j.connect()

        neighbors = await neo4j.get_entity_neighbors(entity_name, depth)

        await neo4j.close()

        return {
            "status": "success",
            "entity_name": entity_name,
            "data": neighbors
        }

    except Exception as e:
        logger.error(f"获取实体详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph")
async def get_graph_data(
    limit: int = Query(default=1000, ge=100, le=5000)
):
    """获取图谱可视化数据"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()

        graph_data = await neo4j.export_graph_data(limit=limit)

        await neo4j.close()

        return {
            "status": "success",
            "node_count": len(graph_data.get("nodes", [])),
            "edge_count": len(graph_data.get("edges", [])),
            "data": graph_data
        }

    except Exception as e:
        logger.error(f"获取图谱数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 向量检索 ============

@router.post("/vector-search")
async def vector_search(
    query: str = Query(..., description="搜索查询"),
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    基于向量的语义搜索

    Args:
        query: 搜索查询
        limit: 返回数量
    """
    try:
        # 生成查询向量
        embedding = EmbeddingService()
        query_vector = await embedding.encode_single(query)

        if not query_vector:
            raise HTTPException(status_code=500, detail="向量生成失败")

        # 搜索相似文章
        vector_store = VectorStore(db)
        results = vector_store.search_by_vector(
            query_vector=query_vector,
            limit=limit,
            threshold=0.3
        )

        return {
            "status": "success",
            "query": query,
            "count": len(results),
            "results": results
        }

    except Exception as e:
        logger.error(f"向量搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-vectors")
async def generate_vectors(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None
):
    """
    为文章生成向量

    Args:
        limit: 最大处理数量
    """
    try:
        # 获取还没有向量的文章
        query = text("""
            SELECT a.id FROM articles a
            LEFT JOIN article_embeddings e ON a.id = e.article_id
            WHERE e.article_id IS NULL AND a.status = 'completed'
            ORDER BY a.scraped_at DESC
            LIMIT :limit
        """)
        from sqlalchemy import text
        result = db.execute(query, {"limit": limit})
        article_ids = [row[0] for row in result.fetchall()]

        if not article_ids:
            return {"status": "success", "message": "没有需要生成向量的文章", "count": 0}

        # 初始化向量服务
        embedding = EmbeddingService()
        vector_store = VectorStore(db)

        # 确保表存在
        vector_store.init_table()

        success = 0
        failed = 0
        errors = []

        for article_id in article_ids:
            try:
                article = db.query(Article).filter(Article.id == article_id).first()
                if not article:
                    continue

                # 生成向量
                title = article.title or ""
                content = article.content or article.summary or ""
                summary = article.summary or ""

                title_vec = await embedding.encode_single(title) if title else []
                content_vec = await embedding.encode_single(content[:5000]) if content else []
                summary_vec = await embedding.encode_single(summary) if summary else []

                if title_vec and content_vec:
                    vector_store.save_embeddings(
                        article_id=article_id,
                        title_vector=title_vec,
                        content_vector=content_vec,
                        summary_vector=summary_vec if summary_vec else None
                    )
                    success += 1
                else:
                    failed += 1

                # 添加小延迟
                await asyncio.sleep(0.2)

            except Exception as e:
                failed += 1
                errors.append({"article_id": article_id, "error": str(e)})
                logger.error(f"生成向量失败 {article_id}: {e}")

        return {
            "status": "success",
            "total": len(article_ids),
            "success": success,
            "failed": failed,
            "errors": errors[:10]  # 只返回前10个错误
        }

    except Exception as e:
        logger.error(f"批量生成向量失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ 删除功能 ============

@router.delete("/article/{article_id}")
async def delete_article_kg(article_id: str):
    """删除文章的图谱数据(保留 Article 节点,清实体关联)"""
    try:
        neo4j = Neo4jService()
        await neo4j.connect()

        await neo4j.delete_article_kg(article_id)

        await neo4j.close()

        return {
            "status": "success",
            "message": f"已删除文章 {article_id} 的图谱数据"
        }

    except Exception as e:
        logger.error(f"删除文章的图谱数据失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ KG ↔ 文档管理 一致性同步(新增) ============

@router.get("/sync-status")
async def get_sync_status(db: Session = Depends(get_db)):
    """
    同步状态总览(供前端轮询,建议每 5~10s 拉一次)
    - by_status: 各 kg_status 的文章计数
    - sync_state: 后台任务进度(in_progress、active_count、本次已处理 / 失败)
    - drift: 数量对比(SQLite vs Neo4j)
    """
    try:
        from sqlalchemy import func
        from app.services.kg_sync import get_sync_state

        # 1. 按 kg_status 统计(SQLite)
        rows = db.query(Article.kg_status, func.count(Article.id)) \
            .filter(Article.status == "success") \
            .group_by(Article.kg_status).all()
        by_status = {
            (r[0] or "pending"): r[1] for r in rows
        }
        # 缺位补 0,统一六个 key
        normalized = {
            "pending": by_status.get("pending", 0) + by_status.get(None, 0),
            "processing": by_status.get("processing", 0),
            "success": by_status.get("success", 0),
            "failed": by_status.get("failed", 0),
            "partial": by_status.get("partial", 0),
            "skipped": by_status.get("skipped", 0),
        }
        total_in_db = sum(normalized.values())
        failed_articles = [
            {
                "id": str(article.id),
                "title": article.title,
                "error": article.kg_error_message,
            }
            for article in db.query(Article)
            .filter(Article.status == "success", Article.kg_status == "failed")
            .order_by(Article.updated_at.desc())
            .limit(20)
            .all()
        ]
        partial_articles = [
            {
                "id": str(article.id),
                "title": article.title,
                "warning": article.kg_error_message,
            }
            for article in db.query(Article)
            .filter(Article.status == "success", Article.kg_status == "partial")
            .order_by(Article.updated_at.desc())
            .limit(20)
            .all()
        ]

        # 2. Neo4j Article 数 + 孤立实体数 + 漂移检测
        neo4j = Neo4jService()
        await neo4j.connect()
        async with neo4j._driver.session() as s:
            r = await s.run("MATCH (a:Article) RETURN count(a) AS c")
            rec = await r.single()
            total_in_kg = rec["c"] if rec else 0
            r_orphan = await s.run("""
                MATCH (e:Entity)
                WHERE NOT (e)<-[:CONTAINS_ENTITY]-(:Article)
                RETURN count(e) AS c
            """)
            rec_orphan = await r_orphan.single()
            orphan_entities = rec_orphan["c"] if rec_orphan else 0
        await neo4j.close()

        return {
            "status": "success",
            "by_status": normalized,
            "total_in_db": total_in_db,
            "total_in_kg": total_in_kg,
            "orphan_entities": orphan_entities,
            "drift_detected": total_in_db != total_in_kg or orphan_entities > 0,
            "failed_articles": failed_articles,
            "partial_articles": partial_articles,
            "sync_state": get_sync_state(),
        }
    except Exception as e:
        logger.error(f"获取同步状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reconcile")
async def reconcile_knowledge_graph(
    apply: bool = Query(default=False, description="是否自动修复"),
    db: Session = Depends(get_db)
):
    """
    对账:对比 SQLite 与 Neo4j
    - apply=false: 仅返回漂移报告
    - apply=true:  自动修复(missing → 异步抽; orphan → 删; dirty → 标 pending)
    """
    try:
        result = await kg_sync.reconcile(apply=apply, db=db)
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"对账失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup-orphans")
async def cleanup_orphan_entities():
    """删除没有任何 Article 入边的孤立 Entity 节点及其关系。"""
    neo4j = Neo4jService()
    try:
        await neo4j.connect()
        deleted = await neo4j.cleanup_orphan_entities()
        stats = await neo4j.get_graph_stats()
        return {
            "status": "success",
            "deleted": deleted,
            "stats": stats,
        }
    except Exception as e:
        logger.error(f"清理孤立实体失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        await neo4j.close()


@router.post("/process-pending")
async def process_pending_articles_now(
    limit: int = Query(default=200, ge=1, le=1000, description="最多处理多少篇"),
    max_concurrency: int = Query(default=3, ge=1, le=10, description="并发数"),
    include_failed: bool = Query(default=True, description="是否同时重试失败文章"),
    include_success: bool = Query(default=False, description="是否安全重建已成功文章的证据"),
    db: Session = Depends(get_db)
):
    """
    立即触发:把 kg_status in (NULL, 'pending', 'skipped') 的文章批量抽实体。
    复用启动时的 process_pending_articles,带并发和限流,不会打爆 LLM。
    """
    try:
        result = await kg_sync.process_pending_articles(
            db=db,
            max_concurrency=max_concurrency,
            rate_limit_seconds=0.5,
            limit=limit,
            include_failed=include_failed,
            include_success=include_success,
        )
        return {"status": "success", **result}
    except Exception as e:
        logger.error(f"立即抽取失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reprocess/{article_id}")
async def reprocess_article(article_id: str, db: Session = Depends(get_db)):
    """重抽单篇文章:清旧实体+关系,重新走 extract_and_link_entities"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    try:
        # 先抽取，解析成功后由同步服务原子式替换旧知识，避免失败重抽清空可用数据。
        article.kg_status = "pending"
        article.kg_error_message = None
        db.commit()

        await kg_sync.extract_and_link_entities(article_id)
        db.expire_all()
        refreshed = db.query(Article).filter(Article.id == article_id).first()
        final_status = refreshed.kg_status if refreshed else "failed"
        return {
            "status": "success" if final_status == "success" else "failed",
            "article_id": article_id,
            "kg_status": final_status,
            "error": refreshed.kg_error_message if refreshed else "文章不存在",
            "message": "重抽完成" if final_status == "success" else "重抽失败",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重抽失败 {article_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/article/{article_id}/status")
async def get_article_kg_status(article_id: str, db: Session = Depends(get_db)):
    """获取文章在 KG 中的状态(用于前端轮询)"""
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="文章不存在")

    # 查询 Neo4j 实体 / 关系数
    entity_count = 0
    relation_count = 0
    try:
        neo4j = Neo4jService()
        await neo4j.connect()
        async with neo4j._driver.session() as session:
            r1 = await session.run("""
                MATCH (a:Article {id: $id})-[:CONTAINS_ENTITY]->(e:Entity)
                RETURN count(e) AS c
            """, id=article_id)
            rec1 = await r1.single()
            entity_count = rec1["c"] if rec1 else 0
            r2 = await session.run("""
                MATCH (a:Article {id: $id})-[:CONTAINS_ENTITY]->(e1:Entity)
                      (e1)-[r:RELATES_TO]->(e2:Entity)
                RETURN count(r) AS c
            """, id=article_id)
            rec2 = await r2.single()
            relation_count = rec2["c"] if rec2 else 0
        await neo4j.close()
    except Exception as e:
        logger.warning(f"查询 KG 实体/关系数失败 {article_id}: {e}")

    return {
        "status": "success",
        "article_id": article_id,
        "kg_status": article.kg_status,
        "kg_processed_at": article.kg_processed_at.isoformat() if article.kg_processed_at else None,
        "kg_error_message": article.kg_error_message,
        "entity_count": entity_count,
        "relation_count": relation_count
    }


# ==================== 对话页 KG 问答 (M1) ====================

class QARequest(BaseModel):
    question: str
    model_id: str = "default"
    session_id: Optional[str] = None


class PathExploreRequest(BaseModel):
    source: str
    target: str
    max_depth: int = 4
    limit: int = 10
    relation_types: List[str] = Field(default_factory=list)


@router.post("/explore/path")
async def explore_shortest_path(
    request: PathExploreRequest,
    db: Session = Depends(get_db),
):
    """查找实体间可解释最短路径，并补充路径所引用的文章元数据。"""
    source = request.source.strip()
    target = request.target.strip()
    if not source or not target:
        raise HTTPException(status_code=400, detail="起点和终点实体不能为空")
    if source == target:
        raise HTTPException(status_code=400, detail="起点和终点不能相同")

    neo4j = Neo4jService()
    try:
        paths = await neo4j.find_shortest_paths(
            source_name=source,
            target_name=target,
            max_depth=request.max_depth,
            limit=request.limit,
            relation_types=request.relation_types,
        )
    finally:
        await neo4j.close()

    article_ids = {
        article_id
        for path in paths
        for rel in path.get("relationships", [])
        for article_id in rel.get("source_articles", [])
    }
    articles = []
    if article_ids:
        rows = db.query(Article).filter(Article.id.in_(article_ids)).all()
        articles = [
            {
                "id": str(article.id),
                "title": article.title,
                "url": article.url,
                "published_at": article.published_at.isoformat()
                if article.published_at else None,
            }
            for article in rows
        ]

    return {
        "status": "success",
        "source": source,
        "target": target,
        "count": len(paths),
        "paths": paths,
        "articles": articles,
    }


@router.get("/explore/entity-profile/{entity_name}")
async def explore_entity_profile(
    entity_name: str,
    neighbor_limit: int = Query(default=20, ge=1, le=100),
    evidence_limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """返回实体跨文档档案、邻居关系和原文证据。"""
    neo4j = Neo4jService()
    try:
        profile = await neo4j.get_entity_profile(
            entity_name=entity_name,
            neighbor_limit=neighbor_limit,
            evidence_limit=evidence_limit,
        )
    finally:
        await neo4j.close()
    if not profile:
        raise HTTPException(status_code=404, detail="实体不存在")

    article_ids = profile.pop("article_ids", [])
    article_rows = db.query(Article).filter(Article.id.in_(article_ids)).all() \
        if article_ids else []
    articles_by_id = {str(article.id): article for article in article_rows}
    profile["articles"] = [
        {
            "id": article_id,
            "title": articles_by_id[article_id].title,
            "url": articles_by_id[article_id].url,
            "summary": articles_by_id[article_id].summary,
            "published_at": articles_by_id[article_id].published_at.isoformat()
            if articles_by_id[article_id].published_at else None,
        }
        for article_id in article_ids
        if article_id in articles_by_id
    ]
    return {"status": "success", **profile}


class AliasReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    decision: Literal["approved", "rejected"]
    canonical_name: Optional[str] = Field(default=None, max_length=500)
    note: str = Field(default="", max_length=500)


class CrossDocumentReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


class LegacyRelationReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    rel_type: str = Field(min_length=1, max_length=100)
    decision: Literal["kept", "deleted"]
    note: str = Field(default="", max_length=500)


class InferenceReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    rel_type: Literal["part_of", "located_in", "precedes", "succeeds"]
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


class LinkPredictionReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


class CausalReviewRequest(BaseModel):
    source: str = Field(min_length=1, max_length=500)
    target: str = Field(min_length=1, max_length=500)
    rel_type: Literal["causes", "enables"]
    decision: Literal["approved", "rejected"]
    note: str = Field(default="", max_length=500)


@router.get("/mining/reviews")
async def get_mining_reviews(
    review_type: Optional[str] = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
):
    neo4j = Neo4jService()
    try:
        reviews = await neo4j.get_mining_reviews(review_type=review_type, limit=limit)
        return {"status": "success", "count": len(reviews), "reviews": reviews}
    finally:
        await neo4j.close()


@router.post("/mining/reviews/{review_id}/undo")
async def undo_mining_review(review_id: str):
    neo4j = Neo4jService()
    try:
        review = await neo4j.undo_mining_review(review_id)
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/aliases")
async def get_alias_candidates(
    min_shared_articles: int = Query(default=2, ge=1, le=20),
    min_score: float = Query(default=0.32, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=200),
    include_reviewed: bool = Query(default=False),
):
    """返回待人工确认的实体别名候选，不自动合并。"""
    neo4j = Neo4jService()
    try:
        candidates = await neo4j.get_alias_candidates(
            min_shared_articles=min_shared_articles,
            min_score=min_score,
            limit=limit,
            include_reviewed=include_reviewed,
        )
        return {"status": "success", "count": len(candidates), "candidates": candidates}
    finally:
        await neo4j.close()


@router.post("/mining/aliases/review")
async def review_alias_candidate(request: AliasReviewRequest):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_alias_candidate(
            source=request.source.strip(),
            target=request.target.strip(),
            decision=request.decision,
            canonical_name=request.canonical_name.strip() if request.canonical_name else None,
            note=request.note.strip(),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.post("/mining/backfill-legacy-evidence")
async def backfill_legacy_relation_evidence(
    apply: bool = Query(default=False),
    limit: int = Query(default=500, ge=1, le=5000),
    db: Session = Depends(get_db),
):
    """从同时包含两端实体的原文句子中恢复旧关系证据。"""
    neo4j = Neo4jService()
    try:
        relations = await neo4j.get_legacy_relations(limit=limit)
        article_ids = {
            article_id
            for relation in relations
            for article_id in set(relation.get("source_article_ids") or [])
                & set(relation.get("target_article_ids") or [])
        }
        articles = db.query(Article).filter(Article.id.in_(article_ids)).all() \
            if article_ids else []
        article_by_id = {str(article.id): article for article in articles}
        recovered = []

        for relation in relations:
            shared_ids = sorted(
                set(relation.get("source_article_ids") or [])
                & set(relation.get("target_article_ids") or [])
            )
            for article_id in shared_ids:
                article = article_by_id.get(str(article_id))
                if not article:
                    continue
                evidence = find_relation_evidence(
                    article.content or "",
                    relation["source"],
                    relation["target"],
                )
                if not evidence:
                    continue
                item = {
                    "source": relation["source"],
                    "target": relation["target"],
                    "rel_type": relation["rel_type"],
                    "article_id": str(article_id),
                    "article_title": article.title,
                    "evidence": evidence,
                }
                if apply:
                    item["applied"] = await neo4j.add_recovered_relation_evidence(
                        source=relation["source"],
                        target=relation["target"],
                        rel_type=relation["rel_type"],
                        article_id=str(article_id),
                        evidence=evidence,
                        confidence=relation.get("confidence") or 0.6,
                    )
                recovered.append(item)
                break

        return {
            "status": "success",
            "applied": apply,
            "legacy_scanned": len(relations),
            "recoverable": len(recovered),
            "remaining": len(relations) - len(recovered),
            "recovered": recovered,
        }
    finally:
        await neo4j.close()


@router.get("/mining/cross-document")
async def get_cross_document_candidates(
    min_shared_articles: int = Query(default=2, ge=2, le=20),
    limit: int = Query(default=50, ge=1, le=200),
    include_reviewed: bool = Query(default=False),
):
    """返回跨文档稳定共现但尚无显式关系的实体对。"""
    neo4j = Neo4jService()
    try:
        candidates = await neo4j.get_cross_document_candidates(
            min_shared_articles=min_shared_articles,
            limit=limit,
            include_reviewed=include_reviewed,
        )
        return {"status": "success", "count": len(candidates), "candidates": candidates}
    finally:
        await neo4j.close()


@router.post("/mining/cross-document/review")
async def review_cross_document_candidate(request: CrossDocumentReviewRequest):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_cross_document_candidate(
            source=request.source.strip(),
            target=request.target.strip(),
            decision=request.decision,
            note=request.note.strip(),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/legacy-relations")
async def get_legacy_relations(limit: int = Query(default=100, ge=1, le=1000)):
    neo4j = Neo4jService()
    try:
        relations = await neo4j.get_legacy_relations(limit=limit)
        return {"status": "success", "count": len(relations), "relations": relations}
    finally:
        await neo4j.close()


@router.post("/mining/legacy-relations/review")
async def review_legacy_relation(request: LegacyRelationReviewRequest):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_legacy_relation(
            source=request.source.strip(),
            target=request.target.strip(),
            rel_type=request.rel_type.strip(),
            decision=request.decision,
            note=request.note.strip(),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/communities")
async def get_communities(
    min_size: int = Query(default=3, ge=2, le=100),
    limit: int = Query(default=20, ge=1, le=100),
):
    """执行轻量标签传播，返回实体社区。"""
    neo4j = Neo4jService()
    try:
        communities = await neo4j.get_communities(min_size=min_size, limit=limit)
        return {"status": "success", "count": len(communities), "communities": communities}
    finally:
        await neo4j.close()


@router.get("/mining/inferences")
async def get_transitive_inferences(
    relation_types: List[str] = Query(default=[]),
    max_hops: int = Query(default=3, ge=2, le=5),
    limit: int = Query(default=100, ge=1, le=500),
):
    """返回带完整关系链和来源文章的传递规则候选，不自动写图。"""
    allowed = {"part_of", "located_in", "precedes", "succeeds"}
    requested = relation_types or sorted(allowed)
    invalid = sorted(set(requested) - allowed)
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的传递关系: {', '.join(invalid)}")
    neo4j = Neo4jService()
    try:
        inferences = await neo4j.get_transitive_inferences(
            relation_types=requested,
            max_hops=max_hops,
            limit=limit,
        )
        return {"status": "success", "count": len(inferences), "inferences": inferences}
    finally:
        await neo4j.close()


@router.post("/mining/inferences/review")
async def review_transitive_inference(request: InferenceReviewRequest):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_inference_candidate(
            source=request.source.strip(),
            target=request.target.strip(),
            rel_type=request.rel_type,
            decision=request.decision,
            note=request.note.strip(),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/link-predictions")
async def get_link_predictions(
    min_common_neighbors: int = Query(default=2, ge=1, le=20),
    min_score: float = Query(default=0.2, ge=0.0, le=1.0),
    limit: int = Query(default=100, ge=1, le=500),
):
    neo4j = Neo4jService()
    try:
        predictions = await neo4j.get_link_predictions(
            min_common_neighbors=min_common_neighbors,
            min_score=min_score,
            limit=limit,
        )
        return {"status": "success", "count": len(predictions), "predictions": predictions}
    finally:
        await neo4j.close()


@router.post("/mining/link-predictions/review")
async def review_link_prediction(request: LinkPredictionReviewRequest):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_link_prediction(
            source=request.source.strip(),
            target=request.target.strip(),
            decision=request.decision,
            note=request.note.strip(),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.post("/mining/embeddings/generate")
async def generate_graph_embeddings(
    dimensions: int = Query(default=16, ge=2, le=64),
):
    neo4j = Neo4jService()
    try:
        result = await neo4j.generate_graph_embeddings(dimensions=dimensions)
        return {"status": "success", **result}
    finally:
        await neo4j.close()


@router.get("/mining/embeddings/status")
async def get_graph_embedding_status():
    neo4j = Neo4jService()
    try:
        result = await neo4j.get_graph_embedding_status()
        return {"status": "success", **result}
    finally:
        await neo4j.close()


@router.get("/mining/embeddings/evaluate")
async def evaluate_graph_embeddings(k: int = Query(default=5, ge=1, le=20)):
    neo4j = Neo4jService()
    try:
        result = await neo4j.evaluate_graph_embeddings(k=k)
        return {"status": "success", **result}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.delete("/mining/embeddings")
async def clear_graph_embeddings():
    neo4j = Neo4jService()
    try:
        cleared = await neo4j.clear_graph_embeddings()
        return {"status": "success", "cleared": cleared}
    finally:
        await neo4j.close()


@router.get("/mining/similar/{entity_name}")
async def get_similar_entities(
    entity_name: str,
    limit: int = Query(default=20, ge=1, le=100),
    same_type: bool = Query(default=True),
    min_score: float = Query(default=0.0, ge=-1.0, le=1.0),
):
    neo4j = Neo4jService()
    try:
        result = await neo4j.get_similar_entities(
            entity_name=entity_name,
            limit=limit,
            same_type=same_type,
            min_score=min_score,
        )
        return {"status": "success", **result}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/causal-candidates")
async def get_causal_candidates(
    limit: int = Query(default=100, ge=1, le=500),
    include_history: bool = Query(default=True),
    db: Session = Depends(get_db),
):
    neo4j = Neo4jService()
    try:
        articles = get_causal_article_records(db) if include_history else None
        candidates = await neo4j.get_causal_candidates(limit=limit, articles=articles)
        return {"status": "success", "count": len(candidates), "candidates": candidates}
    finally:
        await neo4j.close()


@router.post("/mining/causal-candidates/review")
async def review_causal_candidate(
    request: CausalReviewRequest,
    db: Session = Depends(get_db),
):
    neo4j = Neo4jService()
    try:
        review = await neo4j.review_causal_candidate(
            source=request.source.strip(),
            target=request.target.strip(),
            rel_type=request.rel_type,
            decision=request.decision,
            note=request.note.strip(),
            articles=get_causal_article_records(db),
        )
        return {"status": "success", "review": review}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    finally:
        await neo4j.close()


@router.get("/mining/causal-chains")
async def get_causal_chains(
    source: Optional[str] = Query(default=None, max_length=500),
    target: Optional[str] = Query(default=None, max_length=500),
    max_hops: int = Query(default=4, ge=1, le=6),
    limit: int = Query(default=100, ge=1, le=500),
):
    neo4j = Neo4jService()
    try:
        chains = await neo4j.get_causal_chains(
            source=source,
            target=target,
            max_hops=max_hops,
            limit=limit,
        )
        return {"status": "success", "count": len(chains), "chains": chains}
    finally:
        await neo4j.close()


@router.get("/mining/timeline")
async def get_event_timeline(
    start_date: Optional[date] = Query(default=None),
    end_date: Optional[date] = Query(default=None),
    query: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    neo4j = Neo4jService()
    try:
        events = await neo4j.get_temporal_events(limit=limit)
    finally:
        await neo4j.close()

    article_ids = {
        str(article_id)
        for event in events
        for article_id in event.get("article_ids", [])
        if article_id
    }
    articles = db.query(Article).filter(Article.id.in_(article_ids)).all() if article_ids else []
    article_by_id = {str(article.id): article for article in articles}
    timeline = []
    normalized_query = (query or "").strip().casefold()
    for event in events:
        if normalized_query and normalized_query not in (
            f"{event.get('name', '')} {event.get('description', '')}".casefold()
        ):
            continue
        event_articles = [
            article_by_id[str(article_id)]
            for article_id in event.get("article_ids", [])
            if str(article_id) in article_by_id
        ]
        published_dates = sorted({
            article.published_at for article in event_articles if article.published_at
        })
        observed_at = published_dates[0] if published_dates else None
        if start_date and (not observed_at or observed_at < start_date):
            continue
        if end_date and (not observed_at or observed_at > end_date):
            continue
        timeline.append({
            **event,
            "observed_at": observed_at.isoformat() if observed_at else None,
            "articles": [
                {
                    "id": str(article.id),
                    "title": article.title,
                    "url": article.url,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                }
                for article in event_articles
            ],
        })
    timeline.sort(key=lambda item: (item["observed_at"] is None, item["observed_at"] or "", item["name"]))
    return {"status": "success", "count": len(timeline), "events": timeline[:limit]}


@router.post("/qa/answer")
async def kg_qa_answer(req: QARequest, db: Session = Depends(get_db)):
    """对话页 KG 问答入口"""
    try:
        result = await answer_question(
            question=req.question,
            model_id=req.model_id,
            session_id=req.session_id,
            db=db,
        )
        return result
    except Exception as e:
        logger.error(f"qa/answer 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/entity-context/{entity_name}")
async def get_entity_context(
    entity_name: str,
    limit: int = Query(default=5, ge=1, le=20),
    db: Session = Depends(get_db),
):
    """获取实体的原文出处(出现的文章 + 原文片段)"""
    neo4j = Neo4jService()
    await neo4j.connect()
    try:
        async with neo4j._driver.session() as session:
            r = await session.run(
                "MATCH (e:Entity {name:$n}) "
                "RETURN e.name AS name, e.entity_type AS type, "
                "e.subtype AS subtype, e.description AS description, "
                "e.source_articles AS source_articles",
                n=entity_name,
            )
            row = await r.single()
        if not row:
            return {"entity": {"name": entity_name, "type": None, "subtype": None, "description": None}, "articles": []}

        article_ids = (row["source_articles"] or [])[:limit]
        articles_out = []
        if article_ids:
            arts = db.query(Article).filter(Article.id.in_(article_ids)).all()
            for a in arts:
                text = (a.content or "") + " " + (a.summary or "")
                positions = []
                if entity_name and entity_name in text:
                    start = 0
                    while True:
                        idx = text.find(entity_name, start)
                        if idx < 0:
                            break
                        positions.append([idx, idx + len(entity_name)])
                        start = idx + len(entity_name)
                snippet = ""
                if positions:
                    s, e = positions[0]
                    snippet = text[max(0, s - 60):min(len(text), e + 60)]
                articles_out.append({
                    "article_id": str(a.id),
                    "title": a.title or "(无标题)",
                    "snippet": snippet,
                    "highlight_positions": positions[:5],
                })

        return {
            "entity": {
                "name": row["name"], "type": row["type"],
                "subtype": row["subtype"], "description": row["description"],
            },
            "articles": articles_out,
        }
    finally:
        await neo4j.close()
