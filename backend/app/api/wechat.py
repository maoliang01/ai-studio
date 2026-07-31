# -*- coding: utf-8 -*-
"""
微信公众号 API 路由

提供 Cookie 管理、公众号管理、爬取任务管理等 API
"""

import logging
import uuid
import asyncio
import json
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.wechat import WechatAccount, WechatCookie, WechatCrawlTask
from app.services.wechat.cookie_manager import CookieManager, get_cookie_manager
from app.services.wechat.pipeline import WechatPipeline, get_wechat_pipeline
from app.services.wechat.task_executor import WechatTaskExecutor, get_task_executor
from app.services.wechat.public_discovery import (
    PUBLIC_DISCOVERY_JOBS,
    create_public_discovery_job,
    run_public_discovery_job,
    run_public_ingest_job,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/wechat", tags=["微信公众号"])

# 轻量级进程内任务状态。服务重启后记录会清空，适合当前单机部署。
wechat_crawl_jobs: dict[str, dict] = {}
wechat_discovery_locks: dict[str, asyncio.Lock] = {}


def _format_beijing(value: datetime) -> str:
    return value.replace(tzinfo=timezone.utc).astimezone(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d %H:%M:%S（北京时间）")


async def _run_crawl_job(
    job_id: str,
    pipeline: WechatPipeline,
    urls: List[str],
    category_id: Optional[str],
) -> None:
    job = wechat_crawl_jobs[job_id]
    job["status"] = "running"
    job["started_at"] = datetime.utcnow().isoformat()
    try:
        results = await pipeline.process_batch(urls, 1.0, category_id)
        successful = [item for item in results if item.get("success")]
        failed_results = [item for item in results if not item.get("success")]
        failed = len(failed_results)
        first_error = failed_results[0].get("error") if failed_results else None
        job.update({
            "status": "completed" if successful else "failed",
            "success_count": len(successful),
            "failed_count": failed,
            "results": results,
            "message": (
                f"爬取完成：成功 {len(successful)} 篇，失败 {failed} 篇"
                if successful
                else f"爬取失败：{first_error or '未能获取文章，请检查链接、Cookie 和网络连接'}"
            ),
        })
    except Exception as exc:
        logger.exception("公众号爬取任务失败: %s", job_id)
        job.update({
            "status": "failed",
            "success_count": 0,
            "failed_count": len(urls),
            "message": str(exc) or "爬取任务执行失败",
        })
    finally:
        job["finished_at"] = datetime.utcnow().isoformat()


# ==================== 请求/响应模型 ====================

class CookieCreateRequest(BaseModel):
    """创建 Cookie 请求"""
    name: str = Field(..., min_length=1, max_length=200)
    cookie_data: str = Field(..., description="Cookie JSON 数据")
    expires_at: Optional[datetime] = None


class CookieUpdateRequest(BaseModel):
    """更新 Cookie 请求"""
    name: Optional[str] = None
    cookie_data: Optional[str] = None
    is_active: Optional[bool] = None
    expires_at: Optional[datetime] = None


class AccountCreateRequest(BaseModel):
    """创建公众号请求"""
    name: str = Field(..., min_length=1, max_length=200)
    wechat_id: Optional[str] = None
    description: Optional[str] = None


class AccountFromArticleRequest(BaseModel):
    """通过典型文章链接识别并创建公众号档案。"""
    article_url: str = Field(..., min_length=10, max_length=2000)


class AccountUpdateRequest(BaseModel):
    """更新公众号请求"""
    name: Optional[str] = None
    wechat_id: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class TaskCreateRequest(BaseModel):
    """创建定时任务请求"""
    account_id: str = Field(..., description="公众号 ID")
    schedule_type: str = Field(..., description="定时类型: daily/weekly/monthly")
    schedule_time: Optional[str] = Field(None, description="执行时间 HH:MM")
    max_articles: int = Field(10, ge=1, le=100)
    is_enabled: bool = True


class CrawlRequest(BaseModel):
    """爬取请求"""
    urls: List[str] = Field(..., min_items=1, description="文章 URL 列表")
    category_id: Optional[str] = None


class AccountCrawlRequest(BaseModel):
    """公众号爬取请求"""
    max_articles: int = Field(10, ge=1, le=100)
    category_id: Optional[str] = None


class AccountRangeCrawlRequest(BaseModel):
    """按公众号及日期范围发现并爬取文章。"""
    start_date: date
    end_date: date
    max_articles: int = Field(50, ge=1, le=100)
    category_id: Optional[str] = None
    repeat_interval_minutes: int = Field(60, ge=15, le=1440)


class PublicDiscoveryRequest(BaseModel):
    """通过公开来源发现候选链接，不调用微信后台文章列表接口。"""
    start_date: date
    end_date: date
    seed_urls: List[str] = Field(default_factory=list, max_items=20)
    max_articles: int = Field(30, ge=1, le=50)
    category_id: Optional[str] = None


class PublicDiscoveryIngestRequest(BaseModel):
    urls: List[str] = Field(..., min_items=1, max_items=50)
    category_id: Optional[str] = None


# ==================== Cookie 管理 API ====================

@router.get("/cookies")
async def get_cookies(
    active_only: bool = False,
    db: Session = Depends(get_db)
):
    """获取 Cookie 列表"""
    cookie_manager = get_cookie_manager(db)
    cookies = await cookie_manager.get_cookies(active_only)
    return {"items": [c.to_dict() for c in cookies]}


@router.post("/cookies")
async def create_cookie(
    request: CookieCreateRequest,
    db: Session = Depends(get_db)
):
    """创建 Cookie"""
    cookie_manager = get_cookie_manager(db)
    try:
        cookie = await cookie_manager.create_cookie(
            name=request.name,
            cookie_data=request.cookie_data,
            expires_at=request.expires_at
        )
        return {"success": True, "item": cookie.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/cookies/{cookie_id}")
async def update_cookie(
    cookie_id: str,
    request: CookieUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新 Cookie"""
    cookie_manager = get_cookie_manager(db)
    try:
        cookie = await cookie_manager.update_cookie(
            cookie_id=cookie_id,
            name=request.name,
            cookie_data=request.cookie_data,
            is_active=request.is_active,
            expires_at=request.expires_at,
        )
        if not cookie:
            raise HTTPException(status_code=404, detail="Cookie 不存在")
        return {"success": True, "item": cookie.to_dict()}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/cookies/{cookie_id}")
async def delete_cookie(
    cookie_id: str,
    db: Session = Depends(get_db)
):
    """删除 Cookie"""
    cookie_manager = get_cookie_manager(db)
    success = await cookie_manager.delete_cookie(cookie_id)
    if not success:
        raise HTTPException(status_code=404, detail="Cookie 不存在")
    return {"success": True}


@router.post("/cookies/{cookie_id}/activate")
async def activate_cookie(
    cookie_id: str,
    db: Session = Depends(get_db)
):
    """激活 Cookie"""
    cookie_manager = get_cookie_manager(db)
    cookie = await cookie_manager.activate_cookie(cookie_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="Cookie 不存在")
    return {"success": True, "item": cookie.to_dict()}


@router.post("/cookies/{cookie_id}/deactivate")
async def deactivate_cookie(
    cookie_id: str,
    db: Session = Depends(get_db)
):
    """停用 Cookie"""
    cookie_manager = get_cookie_manager(db)
    cookie = await cookie_manager.deactivate_cookie(cookie_id)
    if not cookie:
        raise HTTPException(status_code=404, detail="Cookie 不存在")
    return {"success": True, "item": cookie.to_dict()}


@router.post("/cookies/{cookie_id}/validate")
async def validate_cookie(
    cookie_id: str,
    db: Session = Depends(get_db)
):
    """验证 Cookie"""
    cookie_manager = get_cookie_manager(db)
    result = await cookie_manager.validate_cookie(cookie_id)
    return result


# ==================== 公众号管理 API ====================

@router.get("/accounts")
async def get_accounts(
    enabled_only: bool = False,
    db: Session = Depends(get_db)
):
    """获取公众号列表"""
    query = db.query(WechatAccount)
    if enabled_only:
        query = query.filter(WechatAccount.is_enabled == True)
    accounts = query.all()
    return {"items": [a.to_dict() for a in accounts]}


@router.post("/accounts")
async def create_account(
    request: AccountCreateRequest,
    db: Session = Depends(get_db)
):
    """创建公众号"""
    account = WechatAccount(
        name=request.name,
        wechat_id=request.wechat_id,
        description=request.description
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return {"success": True, "item": account.to_dict()}


@router.post("/accounts/from-article")
async def create_account_from_article(
    request: AccountFromArticleRequest,
    db: Session = Depends(get_db),
):
    """从公开文章提取公众号名称，并创建或复用公众号档案。"""
    pipeline = get_wechat_pipeline(db)
    try:
        await pipeline.crawler.start()
        profile = await pipeline.crawler.extract_account_profile(request.article_url)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("从文章识别公众号失败: %s", request.article_url)
        raise HTTPException(status_code=400, detail=str(exc) or "从文章识别公众号失败")
    finally:
        await pipeline.crawler.stop()

    account = None
    if profile.get("wechat_id"):
        account = db.query(WechatAccount).filter(WechatAccount.wechat_id == profile["wechat_id"]).first()
    if not account:
        account = db.query(WechatAccount).filter(WechatAccount.name == profile["name"]).first()
    created = False
    description_parts = []
    if profile.get("sample_article_title"):
        description_parts.append(f"典型文章：{profile['sample_article_title']}")
    description_parts.append(f"识别来源：{profile['sample_article_url']}")
    if not account:
        account = WechatAccount(
            name=profile["name"],
            wechat_id=profile.get("wechat_id") or None,
            description="\n".join(description_parts),
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        created = True
    else:
        changed = False
        if profile.get("wechat_id") and account.wechat_id != profile["wechat_id"]:
            account.wechat_id = profile["wechat_id"]
            changed = True
        if not account.description:
            account.description = "\n".join(description_parts)
            changed = True
        if changed:
            account.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(account)

    return {
        "success": True,
        "created": created,
        "message": "公众号档案已创建" if created else "公众号档案已存在，已直接使用",
        "item": account.to_dict(),
        "profile": profile,
    }


@router.put("/accounts/{account_id}")
async def update_account(
    account_id: str,
    request: AccountUpdateRequest,
    db: Session = Depends(get_db)
):
    """更新公众号"""
    account = db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    if request.name is not None:
        account.name = request.name
    if request.wechat_id is not None:
        account.wechat_id = request.wechat_id
    if request.description is not None:
        account.description = request.description
    if request.is_enabled is not None:
        account.is_enabled = request.is_enabled

    account.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(account)
    return {"success": True, "item": account.to_dict()}


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: str,
    db: Session = Depends(get_db)
):
    """删除公众号"""
    account = db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    # 先删除关联的定时任务
    db.query(WechatCrawlTask).filter(WechatCrawlTask.account_id == account_id).delete()

    db.delete(account)
    db.commit()
    return {"success": True}


@router.post("/accounts/{account_id}/crawl")
async def crawl_account(
    account_id: str,
    request: AccountCrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """立即爬取公众号文章"""
    account = db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    # 在后台执行爬取任务
    executor = get_task_executor(db)
    background_tasks.add_task(executor.execute_account_crawl, account_id, request.max_articles)

    return {
        "success": True,
        "message": f"公众号 '{account.name}' 爬取任务已提交",
        "account": account.to_dict()
    }


def _filter_cached_articles(cache: dict, request: AccountRangeCrawlRequest) -> Optional[List[dict]]:
    """缓存覆盖请求日期范围时返回过滤后的文章，否则返回 None。"""
    try:
        cache_start = date.fromisoformat(cache["start_date"])
        cache_end = date.fromisoformat(cache["end_date"])
        if cache_start > request.start_date or cache_end < request.end_date:
            return None
        result = []
        for item in cache.get("items", []):
            published_text = item.get("published_at")
            if published_text:
                published = date.fromisoformat(published_text)
                if published < request.start_date or published > request.end_date:
                    continue
            result.append(item)
        return result[:request.max_articles]
    except (KeyError, TypeError, ValueError):
        return None


def _schedule_range_job(
    account: WechatAccount,
    request: AccountRangeCrawlRequest,
    discovered: List[dict],
    background_tasks: BackgroundTasks,
    db: Session,
    cached: bool,
) -> dict:
    urls = [item["url"] for item in discovered if item.get("url")]
    if not urls:
        source = "缓存结果" if cached else "微信后台文章列表"
        raise HTTPException(
            status_code=404,
            detail=f"指定日期范围内没有文章：{source}已正常返回，但过滤后为 0 篇。这不是访问频率限制。",
        )
    job_id = str(uuid.uuid4())
    wechat_crawl_jobs[job_id] = {
        "job_id": job_id, "status": "pending", "total": len(urls),
        "success_count": 0, "failed_count": 0,
        "message": f"已{'从缓存' if cached else ''}发现 {len(urls)} 篇文章，等待爬取",
        "created_at": datetime.utcnow().isoformat(), "results": [],
        "account_id": account.id, "account_name": account.name,
        "start_date": request.start_date.isoformat(), "end_date": request.end_date.isoformat(),
        "cached": cached,
    }
    background_tasks.add_task(
        _run_crawl_job, job_id, get_wechat_pipeline(db), urls, request.category_id,
    )
    return {
        "success": True, "job_id": job_id, "status": "pending",
        "discovered_count": len(urls), "cached": cached,
        "next_allowed_at": f"{account.next_discovery_at.isoformat()}Z" if account.next_discovery_at else None,
        "message": f"{'已复用缓存并' if cached else '已发现并'}提交 {len(urls)} 篇文章",
    }


async def _crawl_account_range_optimized(
    account: WechatAccount,
    request: AccountRangeCrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session,
) -> dict:
    """低频、串行、可缓存的公众号文章发现。"""
    now = datetime.utcnow()
    account.min_crawl_interval_minutes = request.repeat_interval_minutes
    db.commit()

    cache = {}
    if account.discovery_cache:
        try:
            cache = json.loads(account.discovery_cache)
        except (TypeError, json.JSONDecodeError):
            cache = {}
    cached_articles = _filter_cached_articles(cache, request)
    if cached_articles is not None and account.next_discovery_at and account.next_discovery_at > now:
        return _schedule_range_job(account, request, cached_articles, background_tasks, db, cached=True)

    pipeline = get_wechat_pipeline(db)
    active_cookie = await pipeline.crawler.cookie_manager.get_active_cookie()
    if not active_cookie:
        raise HTTPException(status_code=400, detail="没有可用的公众号管理后台 Cookie。")
    cookie_check = await pipeline.crawler.cookie_manager.validate_cookie(active_cookie.id)
    if not cookie_check.get("valid"):
        raise HTTPException(status_code=400, detail=f"当前 Cookie 不可用：{cookie_check.get('message')}")

    if active_cookie.next_discovery_at and active_cookie.next_discovery_at > now:
        retry_seconds = max(1, int((active_cookie.next_discovery_at - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            headers={"Retry-After": str(retry_seconds)},
            detail=(
                f"当前 Cookie“{active_cookie.name}”处于全局冷却期，该 Cookie 下所有公众号的时间范围发现均已暂停。"
                f"下次允许爬取时间：{_format_beijing(active_cookie.next_discovery_at)}。"
            ),
        )

    if account.next_discovery_at and account.next_discovery_at > now:
        retry_seconds = max(1, int((account.next_discovery_at - now).total_seconds()))
        raise HTTPException(
            status_code=429,
            headers={"Retry-After": str(retry_seconds)},
            detail=(
                f"重复访问周期尚未结束，下次允许访问微信后台的时间为 "
                f"{_format_beijing(account.next_discovery_at)}。当前请求无法由缓存覆盖。"
            ),
        )

    lock = wechat_discovery_locks.setdefault(f"cookie:{active_cookie.id}", asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail=f"Cookie“{active_cookie.name}”已有一个公众号发现任务正在执行，其他公众号请排队等待。")

    async with lock:
        try:
            discovered = await pipeline.crawler.discover_account_articles(
                account_name=account.name,
                wechat_id=account.wechat_id or "",
                start_date=request.start_date,
                end_date=request.end_date,
                max_articles=request.max_articles,
                known_fakeid=account.fakeid or "",
            )
        except HTTPException:
            raise
        except Exception as exc:
            account.last_discovery_at = now
            account.last_discovery_status = "failed"
            account.next_discovery_at = now + timedelta(minutes=request.repeat_interval_minutes)
            active_cookie.last_discovery_at = now
            active_cookie.last_discovery_status = "failed"
            active_cookie.next_discovery_at = now + timedelta(minutes=request.repeat_interval_minutes)
            db.commit()
            raise HTTPException(status_code=400, detail=str(exc) or "公众号文章发现失败")
        finally:
            pass

        info = pipeline.crawler.discovery_info
        frequency_limited = (
            info.get("response_ret") == 200013
            or "freq control" in str(info.get("response_error", "")).lower()
        )
        account.last_discovery_at = now
        active_cookie.last_discovery_at = now
        if frequency_limited:
            active_cookie.rate_limit_count = (active_cookie.rate_limit_count or 0) + 1
            account.rate_limit_count = active_cookie.rate_limit_count
            backoff_minutes = min(240, 15 * (2 ** (active_cookie.rate_limit_count - 1)))
            cooldown_minutes = max(request.repeat_interval_minutes, backoff_minutes)
            account.fakeid = info.get("fakeid") or account.fakeid
            account.next_discovery_at = now + timedelta(minutes=cooldown_minutes)
            account.last_discovery_status = "rate_limited"
            active_cookie.next_discovery_at = account.next_discovery_at
            active_cookie.last_discovery_status = "rate_limited"
            db.commit()
            raise HTTPException(
                status_code=429,
                headers={"Retry-After": str(cooldown_minutes * 60)},
                detail=(
                    f"微信后台触发访问频率限制（ret=200013），文章列表未返回，日期过滤尚未执行。"
                    f"系统已停止请求并冷却 {cooldown_minutes} 分钟，下次可尝试时间："
                    f"{_format_beijing(account.next_discovery_at)}。"
                ),
            )

        if info.get("response_ret") not in (None, 0):
            account.last_discovery_status = "backend_error"
            account.next_discovery_at = now + timedelta(minutes=request.repeat_interval_minutes)
            active_cookie.last_discovery_status = "backend_error"
            active_cookie.next_discovery_at = account.next_discovery_at
            db.commit()
            raise HTTPException(
                status_code=502,
                detail=f"微信后台返回错误：{info.get('response_error') or '未知错误'}（ret={info.get('response_ret')}）。",
            )

        account.fakeid = info.get("fakeid") or account.fakeid
        account.rate_limit_count = 0
        account.last_discovery_status = "success" if discovered else "no_articles"
        account.next_discovery_at = now + timedelta(minutes=request.repeat_interval_minutes)
        active_cookie.rate_limit_count = 0
        active_cookie.last_discovery_status = "success"
        active_cookie.next_discovery_at = account.next_discovery_at
        account.discovery_cache = json.dumps({
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "fetched_at": now.isoformat(),
            "items": discovered,
        }, ensure_ascii=False)
        db.commit()
        db.refresh(account)
        return _schedule_range_job(account, request, discovered, background_tasks, db, cached=False)


@router.post("/accounts/{account_id}/crawl-range")
async def crawl_account_range(
    account_id: str,
    request: AccountRangeCrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """发现并爬取公众号在指定日期范围内的历史文章。"""
    if request.start_date > request.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    account = db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    return await _crawl_account_range_optimized(account, request, background_tasks, db)

    discovery_pipeline = get_wechat_pipeline(db)
    active_cookie = await discovery_pipeline.crawler.cookie_manager.get_active_cookie()
    if not active_cookie:
        raise HTTPException(
            status_code=400,
            detail="没有可用的公众号管理后台 Cookie。请先登录微信公众平台，在 URL 带 token 的后台页面导出 Cookie。",
        )
    cookie_check = await discovery_pipeline.crawler.cookie_manager.validate_cookie(active_cookie.id)
    if not cookie_check.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=f"当前 Cookie“{active_cookie.name}”不可用于时间段爬取：{cookie_check.get('message', '缺少公众号管理后台登录凭证')}",
        )
    try:
        await discovery_pipeline.crawler.start()
        discovered = await discovery_pipeline.crawler.discover_account_articles(
            account_name=account.name,
            wechat_id=account.wechat_id or "",
            start_date=request.start_date,
            end_date=request.end_date,
            max_articles=request.max_articles,
        )
    except Exception as exc:
        logger.exception("公众号文章发现失败: %s", account_id)
        raise HTTPException(status_code=400, detail=str(exc) or "公众号文章发现失败")
    finally:
        await discovery_pipeline.crawler.stop()

    urls = [item["url"] for item in discovered]
    if not urls:
        info = discovery_pipeline.crawler.discovery_info
        matched_name = info.get("matched_name") or account.name
        observed_range = ""
        if info.get("latest_date"):
            observed_range = (
                f"；本次后台列表已检查到的日期范围为 "
                f"{info.get('oldest_date') or info['latest_date']} 至 {info['latest_date']}"
            )
        backend_error = ""
        frequency_limited = (
            info.get("response_ret") == 200013
            or "freq control" in str(info.get("response_error", "")).lower()
        )
        if frequency_limited:
            backend_error = "；微信后台触发访问频率限制，请等待几分钟后重试（这不是日期识别错误）"
        elif info.get("response_error") or info.get("response_ret") not in (None, 0):
            backend_error = (
                f"；微信后台返回：{info.get('response_error') or '未知错误'}"
                f"（ret={info.get('response_ret')}）"
            )
        next_step = (
            "请稍后重试，避免连续提交相同任务。"
            if frequency_limited
            else "请确认目标文章页面显示的公众号名称与所选档案完全一致。"
        )
        raise HTTPException(
            status_code=404,
            detail=(
                f"公众号“{matched_name}”在 {request.start_date} 至 {request.end_date} 内没有发现文章"
                f"{observed_range}{backend_error}。{next_step}"
            ),
        )

    job_id = str(uuid.uuid4())
    wechat_crawl_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "total": len(urls),
        "success_count": 0,
        "failed_count": 0,
        "message": f"已发现 {len(urls)} 篇文章，等待爬取",
        "created_at": datetime.utcnow().isoformat(),
        "results": [],
        "account_id": account_id,
        "account_name": account.name,
        "start_date": request.start_date.isoformat(),
        "end_date": request.end_date.isoformat(),
    }
    pipeline = get_wechat_pipeline(db)
    background_tasks.add_task(
        _run_crawl_job,
        job_id,
        pipeline,
        urls,
        request.category_id,
    )
    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "discovered_count": len(urls),
        "message": f"已发现并提交 {len(urls)} 篇文章",
    }


# ==================== 定时任务 API ====================

@router.post("/accounts/{account_id}/public-discovery")
async def start_public_discovery(
    account_id: str,
    request: PublicDiscoveryRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """启动独立的公开来源发现任务；不会调用微信后台文章列表接口。"""
    if request.start_date > request.end_date:
        raise HTTPException(status_code=400, detail="开始日期不能晚于结束日期")
    account = db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    job = create_public_discovery_job()
    background_tasks.add_task(
        run_public_discovery_job,
        job["job_id"],
        db,
        account,
        request.start_date,
        request.end_date,
        request.seed_urls,
        request.max_articles,
        request.category_id,
    )
    return {
        "success": True,
        "job_id": job["job_id"],
        "status": "pending",
        "message": "公开来源发现任务已提交；该模式不会调用微信后台文章列表接口。",
    }


@router.get("/public-discovery/{job_id}")
async def get_public_discovery_job(job_id: str):
    job = PUBLIC_DISCOVERY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="公开来源发现任务不存在或服务已重启")
    return job


@router.post("/public-discovery/{job_id}/ingest")
async def ingest_public_discovery_candidates(
    job_id: str,
    request: PublicDiscoveryIngestRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    job = PUBLIC_DISCOVERY_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="公开来源发现任务不存在或服务已重启")
    if job.get("status") not in {"completed", "ingested", "failed"}:
        raise HTTPException(status_code=409, detail="候选文章尚未发现完成或正在入库")
    candidate_urls = {item.get("url") for item in job.get("candidates", [])}
    selected_urls = list(dict.fromkeys(request.urls))
    unknown_urls = [url for url in selected_urls if url not in candidate_urls]
    if unknown_urls:
        raise HTTPException(status_code=400, detail="所选链接中包含不属于当前任务的候选文章")
    background_tasks.add_task(
        run_public_ingest_job, job_id, db, selected_urls, request.category_id
    )
    return {
        "success": True,
        "job_id": job_id,
        "status": "ingesting",
        "message": f"已提交 {len(selected_urls)} 篇候选文章入库。",
    }


@router.get("/tasks")
async def get_tasks(
    db: Session = Depends(get_db)
):
    """获取定时任务列表"""
    tasks = db.query(WechatCrawlTask).all()
    return {"items": [t.to_dict() for t in tasks]}


@router.post("/tasks")
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db)
):
    """创建定时任务"""
    # 验证公众号是否存在
    account = db.query(WechatAccount).filter(WechatAccount.id == request.account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="公众号不存在")

    task = WechatCrawlTask(
        account_id=request.account_id,
        schedule_type=request.schedule_type,
        schedule_time=request.schedule_time,
        max_articles=request.max_articles,
        is_enabled=request.is_enabled
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return {"success": True, "item": task.to_dict()}


@router.put("/tasks/{task_id}")
async def update_task(
    task_id: str,
    request: TaskCreateRequest,
    db: Session = Depends(get_db)
):
    """更新定时任务"""
    task = db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.account_id = request.account_id
    task.schedule_type = request.schedule_type
    task.schedule_time = request.schedule_time
    task.max_articles = request.max_articles
    task.is_enabled = request.is_enabled
    task.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return {"success": True, "item": task.to_dict()}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """删除定时任务"""
    task = db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    db.delete(task)
    db.commit()
    return {"success": True}


@router.post("/tasks/{task_id}/toggle")
async def toggle_task(
    task_id: str,
    db: Session = Depends(get_db)
):
    """启用/禁用定时任务"""
    task = db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    task.is_enabled = not task.is_enabled
    task.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(task)
    return {"success": True, "item": task.to_dict()}


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """立即执行定时任务"""
    task = db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    # 在后台执行爬取任务
    executor = get_task_executor(db)
    background_tasks.add_task(executor.execute_task, task.id)

    task.last_run_at = datetime.utcnow()
    db.commit()

    return {"success": True, "message": "任务已提交执行"}


# ==================== 爬取 API ====================

@router.post("/crawl")
async def crawl_articles(
    request: CrawlRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """爬取文章"""
    pipeline = get_wechat_pipeline(db)

    job_id = str(uuid.uuid4())
    wechat_crawl_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "total": len(request.urls),
        "success_count": 0,
        "failed_count": 0,
        "message": f"已提交 {len(request.urls)} 篇文章的爬取任务",
        "created_at": datetime.utcnow().isoformat(),
        "results": [],
    }
    background_tasks.add_task(
        _run_crawl_job,
        job_id,
        pipeline,
        request.urls,
        request.category_id,
    )

    return {
        "success": True,
        "job_id": job_id,
        "status": "pending",
        "message": f"已提交 {len(request.urls)} 篇文章的爬取任务"
    }


@router.get("/crawl/status/{job_id}")
async def get_crawl_job_status(job_id: str):
    """查询公众号文章爬取任务状态。"""
    job = wechat_crawl_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="爬取任务不存在或服务已重启")
    return job


@router.post("/crawl/article")
async def crawl_single_article(
    url: str,
    category_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """爬取单篇文章"""
    logger.info(f"收到爬取请求: {url}")
    pipeline = get_wechat_pipeline(db)
    try:
        result = await pipeline.process_article(url, category_id=category_id)
        logger.info(f"爬取结果: {result}")
        return result
    except Exception as e:
        logger.error(f"爬取异常: {e}", exc_info=True)
        return {"success": False, "error": str(e) or repr(e) or "未知错误"}
