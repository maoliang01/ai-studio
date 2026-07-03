"""
定时任务 CRUD API

提供定时爬取任务的增删改查、定时调度和历史记录功能
"""
import logging
import json
from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.scheduled_task import (
    ScheduledTask, ScrapeHistory, TaskStatus
)

logger = logging.getLogger("ai-studio")

router = APIRouter(prefix="/api/scheduled", tags=["定时任务"])


# ============ Pydantic Schemas ============

class ScheduledTaskCreate(BaseModel):
    name: str
    source_ids: Optional[List[str]] = []
    source_id: Optional[str] = None
    custom_url: Optional[str] = None
    schedule_time: str
    scrape_range: Optional[str] = "1d"
    is_enabled: Optional[bool] = True


class ScheduledTaskUpdate(BaseModel):
    name: Optional[str] = None
    source_ids: Optional[List[str]] = None
    source_id: Optional[str] = None
    custom_url: Optional[str] = None
    schedule_time: Optional[str] = None
    scrape_range: Optional[str] = None
    is_enabled: Optional[bool] = None


class SourceBrief(BaseModel):
    id: str
    name: str
    url: str


class ScheduledTaskResponse(BaseModel):
    id: str
    name: str
    source_ids: Optional[List[str]] = []
    source_id: Optional[str] = None
    source: Optional[SourceBrief] = None
    custom_url: Optional[str] = None
    schedule_time: str
    scrape_range: str
    is_enabled: bool
    last_run_at: Optional[str] = None
    next_run_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ScrapeHistoryResponse(BaseModel):
    id: str
    task_id: Optional[str] = None
    url: str
    article_title: Optional[str] = None
    article_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    duration: Optional[float] = None
    articles_count: int = 0
    created_at: Optional[str] = None


class TaskStatsResponse(BaseModel):
    total_tasks: int
    enabled_tasks: int
    today_runs: int
    today_success: int
    today_failed: int


def _calculate_next_run(schedule_time: str) -> datetime:
    """计算下次执行时间"""
    hour, minute = map(int, schedule_time.split(":"))
    now = datetime.now()
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run += timedelta(days=1)
    return next_run


def _task_to_response(task: ScheduledTask, db: Session, include_source: bool = False) -> dict:
    """将任务模型转换为响应字典"""
    source = None
    if task.source_id:
        from app.models.article import ScrapeSource
        src = db.query(ScrapeSource).filter(ScrapeSource.id == task.source_id).first()
        if src:
            source = {"id": src.id, "name": src.name, "url": src.url}

    return {
        "id": task.id,
        "name": task.name,
        "source_ids": task.get_source_ids_list(),
        "source_id": task.source_id,
        "source": source,
        "custom_url": task.custom_url,
        "schedule_time": task.schedule_time,
        "scrape_range": task.scrape_range,
        "is_enabled": task.is_enabled,
        "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
        "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _history_to_response(history: ScrapeHistory) -> dict:
    """将历史记录模型转换为响应字典"""
    duration = None
    if history.started_at and history.finished_at:
        duration = (history.finished_at - history.started_at).total_seconds()

    return {
        "id": history.id,
        "task_id": history.task_id,
        "url": history.url,
        "article_title": history.article_title,
        "article_id": history.article_id,
        "status": history.status,
        "error_message": history.error_message,
        "started_at": history.started_at.isoformat() if history.started_at else None,
        "finished_at": history.finished_at.isoformat() if history.finished_at else None,
        "duration": duration,
        "articles_count": history.articles_count,
        "created_at": history.created_at.isoformat() if history.created_at else None,
    }


# ============ 定时任务 CRUD ============

@router.get("", response_model=List[ScheduledTaskResponse])
async def list_tasks(
    include_disabled: bool = Query(False, description="是否包含已禁用的任务"),
    db: Session = Depends(get_db)
):
    """获取所有定时任务"""
    query = db.query(ScheduledTask)
    if not include_disabled:
        query = query.filter(ScheduledTask.is_enabled == True)
    tasks = query.order_by(ScheduledTask.created_at.desc()).all()
    return [_task_to_response(t, db, include_source=True) for t in tasks]


@router.post("", response_model=ScheduledTaskResponse)
async def create_task(request: ScheduledTaskCreate, db: Session = Depends(get_db)):
    """创建定时任务"""
    # 验证时间格式
    try:
        hour, minute = map(int, request.schedule_time.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time")
    except ValueError:
        raise HTTPException(status_code=400, detail="时间格式错误，请使用 HH:MM 格式")

    # 验证爬取范围
    valid_ranges = ["1d", "7d", "30d"]
    if request.scrape_range and request.scrape_range not in valid_ranges:
        raise HTTPException(status_code=400, detail="爬取范围只能是 1d、7d 或 30d")

    # 处理源ID列表
    source_ids = request.source_ids or []
    if request.source_id:
        source_ids = list(set(source_ids + [request.source_id]))

    # 验证爬取源存在
    for sid in source_ids:
        source = db.query(ScrapeSource).filter(ScrapeSource.id == sid).first()
        if not source:
            raise HTTPException(status_code=400, detail=f"爬取源 {sid} 不存在")

    # 计算下次执行时间
    next_run_at = _calculate_next_run(request.schedule_time)

    # 保存第一个源ID到 source_id 字段（兼容）
    primary_source_id = source_ids[0] if source_ids else None

    task = ScheduledTask(
        name=request.name,
        source_ids=json.dumps(source_ids) if source_ids else None,
        source_id=primary_source_id,
        custom_url=request.custom_url,
        schedule_time=request.schedule_time,
        scrape_range=request.scrape_range,
        is_enabled=request.is_enabled,
        next_run_at=next_run_at,
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # 同步调度器
    _sync_scheduler()

    return _task_to_response(task, db, include_source=True)


def _sync_scheduler():
    """同步调度器任务"""
    try:
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler:
            from app.core.scheduler import sync_scheduler_tasks
            sync_scheduler_tasks(scheduler)
    except Exception:
        pass  # 调度器可能未初始化


@router.get("/{task_id}/sync")
def _sync_scheduler():
    """同步调度器任务"""
    try:
        from app.core.scheduler import get_scheduler
        scheduler = get_scheduler()
        if scheduler:
            from app.core.scheduler import sync_scheduler_tasks
            sync_scheduler_tasks(scheduler)
    except Exception:
        pass  # 调度器可能未初始化


# ============ 爬取历史记录 ============

@router.get("/{task_id}", response_model=ScheduledTaskResponse)
async def get_task(task_id: str, db: Session = Depends(get_db)):
    """获取单个定时任务"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_to_response(task, db)


@router.put("/{task_id}", response_model=ScheduledTaskResponse)
async def update_task(task_id: str, request: ScheduledTaskUpdate, db: Session = Depends(get_db)):
    """更新定时任务"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 验证时间格式
    if request.schedule_time:
        try:
            hour, minute = map(int, request.schedule_time.split(":"))
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError("Invalid time")
        except ValueError:
            raise HTTPException(status_code=400, detail="时间格式错误，请使用 HH:MM 格式")

    # 验证爬取范围
    if request.scrape_range:
        valid_ranges = ["1d", "7d", "30d"]
        if request.scrape_range not in valid_ranges:
            raise HTTPException(status_code=400, detail="爬取范围只能是 1d、7d 或 30d")

    # 处理源ID列表
    if request.source_ids is not None or request.source_id is not None:
        source_ids = request.source_ids or []
        if request.source_id:
            source_ids = list(set(source_ids + [request.source_id]))

        # 验证爬取源
        for sid in source_ids:
            source = db.query(ScrapeSource).filter(ScrapeSource.id == sid).first()
            if not source:
                raise HTTPException(status_code=400, detail=f"爬取源 {sid} 不存在")

        task.source_ids = json.dumps(source_ids) if source_ids else None
        task.source_id = source_ids[0] if source_ids else None

    # 更新字段
    if request.name is not None:
        task.name = request.name
    if request.custom_url is not None:
        task.custom_url = request.custom_url
    if request.schedule_time is not None:
        task.schedule_time = request.schedule_time
        task.next_run_at = _calculate_next_run(request.schedule_time)
    if request.scrape_range is not None:
        task.scrape_range = request.scrape_range
    if request.is_enabled is not None:
        task.is_enabled = request.is_enabled

    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # 同步调度器
    _sync_scheduler()

    return _task_to_response(task, db)


@router.delete("/{task_id}")
async def delete_task(task_id: str, db: Session = Depends(get_db)):
    """删除定时任务"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    db.delete(task)
    db.commit()
    return {"message": "任务已删除"}


@router.post("/{task_id}/toggle", response_model=ScheduledTaskResponse)
async def toggle_task(task_id: str, db: Session = Depends(get_db)):
    """切换任务启用状态"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.is_enabled = not task.is_enabled
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)

    # 同步调度器
    _sync_scheduler()

    return _task_to_response(task, db)


@router.post("/{task_id}/run")
async def run_task_now(task_id: str, db: Session = Depends(get_db)):
    """手动触发立即执行任务"""
    task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 获取要爬取的URL列表
    source_ids = task.get_source_ids_list()
    urls = []
    if task.custom_url:
        urls = [task.custom_url]
    else:
        for sid in source_ids:
            source = db.query(ScrapeSource).filter(ScrapeSource.id == sid).first()
            if source:
                urls.append(source.url)

    # 获取爬取范围
    scrape_range = task.scrape_range or "1d"

    if not urls:
        raise HTTPException(status_code=400, detail="任务没有配置爬取URL")

    # 创建历史记录
    history = ScrapeHistory(
        task_id=task_id,
        url=", ".join(urls[:3]) + ("..." if len(urls) > 3 else ""),
        status=TaskStatus.RUNNING.value,
    )
    db.add(history)
    task.last_run_at = datetime.utcnow()
    task.next_run_at = _calculate_next_run(task.schedule_time)
    db.commit()
    db.refresh(history)

    # 在后台运行实际爬取任务
    try:
        from concurrent.futures import ThreadPoolExecutor
        from app.core.scheduler import run_scheduled_task

        executor = ThreadPoolExecutor(max_workers=1)
        executor.submit(run_scheduled_task, task_id)
        executor.shutdown(wait=False)
    except Exception as e:
        logging.getLogger("ai-studio").error(f"启动爬取任务失败: {e}")

    return {
        "message": "任务已开始执行",
        "history_id": history.id,
        "urls": urls,
        "scrape_range": scrape_range,
        "sources_count": len(source_ids),
        "urls": urls,
        "scrape_range": scrape_range,
        "sources_count": len(source_ids),
    }


# ============ 爬取历史记录 ============

@router.get("/history", response_model=List[ScrapeHistoryResponse])
async def list_history(
    task_id: Optional[str] = Query(None, description="按任务ID过滤"),
    status: Optional[str] = Query(None, description="按状态过滤"),
    date: Optional[str] = Query(None, description="按日期过滤，格式 YYYY-MM-DD"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=1, le=200, description="每页数量"),
    db: Session = Depends(get_db)
):
    """获取爬取历史记录"""
    query = db.query(ScrapeHistory)

    if task_id:
        query = query.filter(ScrapeHistory.task_id == task_id)
    if status:
        query = query.filter(ScrapeHistory.status == status)
    if date:
        try:
            filter_date = datetime.strptime(date, "%Y-%m-%d").date()
            query = query.filter(
                ScrapeHistory.started_at >= datetime.combine(filter_date, datetime.min.time()),
                ScrapeHistory.started_at < datetime.combine(filter_date, datetime.max.time())
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    total = query.count()
    histories = query.order_by(ScrapeHistory.started_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return [_history_to_response(h) for h in histories]


@router.get("/history/summary")
async def get_history_summary(
    db: Session = Depends(get_db)
):
    """获取每日爬取汇总（最近7天）"""
    # 获取最近7天的历史记录
    from datetime import timedelta
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = today - timedelta(days=7)

    histories = db.query(ScrapeHistory).filter(
        ScrapeHistory.started_at >= week_ago
    ).order_by(ScrapeHistory.started_at.desc()).all()

    # 按日期分组
    daily_summary = {}
    for h in histories:
        date_str = h.started_at.strftime("%Y-%m-%d")
        if date_str not in daily_summary:
            daily_summary[date_str] = {
                "date": date_str,
                "total": 0,
                "success": 0,
                "failed": 0,
                "articles": 0,
            }
        daily_summary[date_str]["total"] += 1
        if h.status == TaskStatus.SUCCESS.value:
            daily_summary[date_str]["success"] += 1
            daily_summary[date_str]["articles"] += h.articles_count
        elif h.status == TaskStatus.FAILED.value:
            daily_summary[date_str]["failed"] += 1

    return list(daily_summary.values())


@router.get("/stats", response_model=TaskStatsResponse)
async def get_stats(db: Session = Depends(get_db)):
    """获取任务统计"""
    total_tasks = db.query(ScheduledTask).count()
    enabled_tasks = db.query(ScheduledTask).filter(ScheduledTask.is_enabled == True).count()

    # 今日统计
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_histories = db.query(ScrapeHistory).filter(
        ScrapeHistory.started_at >= today
    ).all()

    today_runs = len(today_histories)
    today_success = sum(1 for h in today_histories if h.status == TaskStatus.SUCCESS.value)
    today_failed = sum(1 for h in today_histories if h.status == TaskStatus.FAILED.value)

    return TaskStatsResponse(
        total_tasks=total_tasks,
        enabled_tasks=enabled_tasks,
        today_runs=today_runs,
        today_success=today_success,
        today_failed=today_failed,
    )


@router.delete("/history/{history_id}")
async def delete_history(history_id: str, db: Session = Depends(get_db)):
    """删除历史记录"""
    history = db.query(ScrapeHistory).filter(ScrapeHistory.id == history_id).first()
    if not history:
        raise HTTPException(status_code=404, detail="历史记录不存在")

    db.delete(history)
    db.commit()
    return {"message": "历史记录已删除"}