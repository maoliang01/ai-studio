"""知识增强任务入队与执行。

采集和基础 KG 同步只负责入队；本模块负责持久化任务的领取、执行和恢复。
"""

import asyncio
import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.database import get_session_local
from app.models.article import Article
from app.models.knowledge import KnowledgeJob
from sqlalchemy import or_

logger = logging.getLogger("ai-studio.knowledge_jobs")


def _content_hash(content: str) -> str:
    return hashlib.sha256((content or "").encode("utf-8")).hexdigest()


def enqueue_article_enhancement(
    article_id: str,
    content: Optional[str] = None,
    source_url: Optional[str] = None,
    source_published_at: Optional[str] = None,
) -> Optional[str]:
    """为文章创建幂等增强任务，返回任务 ID。"""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        article = db.query(Article).filter(Article.id == article_id).first()
        if article is not None:
            content = content if content is not None else article.content
            source_url = source_url or article.url
            source_published_at = source_published_at or (
                article.published_at.isoformat() if article.published_at else None
            )
        if not content:
            logger.warning("知识增强入队跳过空文章: %s", article_id)
            return None

        input_hash = _content_hash(content)
        job_id = f"enh_{article_id}_{input_hash[:16]}"
        job = db.query(KnowledgeJob).filter(KnowledgeJob.id == job_id).first()
        if job is None:
            job = KnowledgeJob(
                id=job_id,
                target_id=article_id,
                input_hash=input_hash,
                status="pending",
                progress=0,
            )
            db.add(job)
            db.commit()
            logger.info("知识增强任务已入队: %s", job_id)
        elif job.status in {"pending", "processing", "completed"}:
            return job_id
        else:
            job.status = "pending"
            job.progress = 0
            job.error_message = None
            job.completed_at = None
            job.next_retry_at = None
            db.commit()
            logger.info("知识增强失败任务已重新入队: %s", job_id)
        return job_id
    except Exception:
        db.rollback()
        logger.exception("知识增强任务入队失败: %s", article_id)
        return None
    finally:
        db.close()


def enqueue_synthesis(
    topic: str,
    article_ids: list[str],
    parent_synthesis_id: Optional[str] = None,
) -> str:
    """创建幂等的知识综合异步任务。"""
    raw = "\x1f".join([topic.strip(), parent_synthesis_id or "", *sorted(article_ids)])
    input_hash = _content_hash(raw)
    job_id = f"synth-job-{input_hash[:24]}"
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        job = db.query(KnowledgeJob).filter(KnowledgeJob.id == job_id).first()
        if job is None:
            db.add(KnowledgeJob(
                id=job_id,
                job_type="synthesis",
                target_id=f"synthesis:{topic.strip()}",
                input_hash=input_hash,
                payload={
                    "topic": topic.strip(),
                    "article_ids": article_ids,
                    "parent_synthesis_id": parent_synthesis_id,
                },
                status="pending",
            ))
            db.commit()
        elif job.status in {"failed", "rejected"}:
            job.status = "pending"
            job.progress = 0
            job.error_message = None
            job.completed_at = None
            job.next_retry_at = None
            db.commit()
        return job_id
    finally:
        db.close()


async def _process_job(job_id: str) -> bool:
    """执行单个已领取任务。"""
    from app.core.llm import llm_service
    from app.services.kg import Neo4jService
    from app.services.kg.self_enhancement import KnowledgeSelfEnhancement

    SessionLocal = get_session_local()
    db = SessionLocal()
    neo4j = Neo4jService()
    try:
        job = db.query(KnowledgeJob).filter(KnowledgeJob.id == job_id).first()
        if job is None:
            return False
        if job.job_type == "synthesis":
            from app.services.knowledge_synthesis import KnowledgeSynthesisService
            payload = job.payload or {}
            service = KnowledgeSynthesisService(kg_service=neo4j, llm_client=llm_service)
            synthesis = await service.create_draft(
                db=db,
                topic=payload.get("topic", ""),
                article_ids=payload.get("article_ids", []),
                parent_synthesis_id=payload.get("parent_synthesis_id"),
            )
            job.status = "completed"
            job.progress = 100
            job.result_summary = json.dumps(
                {"synthesis_id": synthesis.id, "status": synthesis.status},
                ensure_ascii=False,
            )
            job.completed_at = datetime.utcnow()
            job.next_retry_at = None
            db.commit()
            return True
        article = db.query(Article).filter(Article.id == job.target_id).first()
        if article is None or not article.content:
            job.status = "failed"
            job.error_message = "文章不存在或内容为空"
            job.completed_at = datetime.utcnow()
            db.commit()
            return False

        service = KnowledgeSelfEnhancement(kg_service=neo4j, llm_client=llm_service)
        result = await service.process_new_article(
            article_id=article.id,
            article_content=article.content,
            source_url=article.url,
            source_published_at=article.published_at.isoformat() if article.published_at else None,
        )
        job.status = result.status
        job.progress = result.progress
        job.result_summary = result.summary
        job.error_message = result.error_message
        job.completed_at = datetime.utcnow() if result.status in {"completed", "failed"} else None
        job.next_retry_at = None
        db.commit()
        return result.status == "completed"
    except Exception as exc:
        db.rollback()
        job = db.query(KnowledgeJob).filter(KnowledgeJob.id == job_id).first()
        if job is not None:
            job.retry_count = (job.retry_count or 0) + 1
            job.error_message = str(exc)[:1000]
            if job.retry_count < (job.max_retries or 0):
                job.status = "pending"
                job.progress = 0
                job.completed_at = None
                delay_seconds = min(900, 30 * (2 ** (job.retry_count - 1)))
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=delay_seconds)
            else:
                job.status = "failed"
                job.completed_at = datetime.utcnow()
                job.next_retry_at = None
            db.commit()
        logger.exception("知识增强任务执行失败: %s", job_id)
        return False
    finally:
        await neo4j.close()
        db.close()


def recover_interrupted_knowledge_jobs() -> int:
    """服务重启后将遗留 processing 任务恢复为 pending。"""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        count = db.query(KnowledgeJob).filter(KnowledgeJob.status == "processing").update(
            {
                KnowledgeJob.status: "pending",
                KnowledgeJob.error_message: "服务重启，任务已恢复",
                KnowledgeJob.next_retry_at: None,
            },
            synchronize_session=False,
        )
        db.commit()
        return count
    finally:
        db.close()


def run_pending_knowledge_jobs(limit: int = 2) -> int:
    """由调度器调用，领取并执行一批待处理任务。"""
    SessionLocal = get_session_local()
    db = SessionLocal()
    try:
        jobs = db.query(KnowledgeJob).filter(
            KnowledgeJob.status == "pending",
            KnowledgeJob.retry_count < KnowledgeJob.max_retries,
            or_(KnowledgeJob.next_retry_at.is_(None), KnowledgeJob.next_retry_at <= datetime.utcnow()),
        ).order_by(KnowledgeJob.created_at.asc()).limit(limit).all()
        job_ids = [job.id for job in jobs]
        for job in jobs:
            job.status = "processing"
            job.started_at = datetime.utcnow()
            job.progress = 1
        db.commit()
    finally:
        db.close()

    completed = 0
    for job_id in job_ids:
        if asyncio.run(_process_job(job_id)):
            completed += 1
    if job_ids:
        logger.info("知识增强任务批次完成: total=%s, completed=%s", len(job_ids), completed)
    return len(job_ids)
