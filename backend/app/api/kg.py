"""
知识图谱 API

提供知识图谱的构建、查询和管理功能
"""
import logging
import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.article import Article
from app.services.kg import Neo4jService, EntityExtractor, EmbeddingService
from app.services.kg.graph import EntityNode, Relationship
from app.services.kg.embedding import VectorStore
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
        stats["drift_detected"] = kg_articles != db_count

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


@router.post("/reprocess/{article_id}")
async def reprocess_article(article_id: str):
    """重抽单篇文章:清旧实体+关系,重新走 extract_and_link_entities"""
    from app.core.database import get_session_local
    SessionLocal = get_session_local()
    session = SessionLocal()
    try:
        article = session.query(Article).filter(Article.id == article_id).first()
        if not article:
            raise HTTPException(status_code=404, detail="文章不存在")
    finally:
        session.close()

    try:
        # 清旧实体(彻底删 Article 节点 + 边 + 孤儿实体)
        neo4j = Neo4jService()
        await neo4j.connect()
        await neo4j.delete_article_full(article_id)
        await neo4j.close()

        # 重置 SQLite 状态,让 extract_and_link_entities 重新走
        article.kg_status = "pending"
        article.kg_error_message = None
        session.commit()
        session.close()

        # 重新抽取
        await kg_sync.extract_and_link_entities(article_id)
        return {"status": "success", "article_id": article_id, "message": "重抽完成"}
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