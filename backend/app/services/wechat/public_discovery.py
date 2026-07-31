# -*- coding: utf-8 -*-
"""Public-source WeChat article discovery.

This module is deliberately independent from the authenticated appmsg/history
discovery flow.  It gathers candidate URLs from public indexes and seed article
pages, then verifies every candidate by fetching the public article page.
"""

from __future__ import annotations

import asyncio
import html
import logging
import re
import uuid
from datetime import date, datetime
from typing import Any, Iterable, Optional
from urllib.parse import quote_plus, unquote, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.wechat import WechatAccount
from app.services.wechat.pipeline import WechatPipeline

logger = logging.getLogger(__name__)

PUBLIC_DISCOVERY_JOBS: dict[str, dict[str, Any]] = {}
WECHAT_URL_RE = re.compile(r"https?://mp\.weixin\.qq\.com/s(?:/|\?)[^\s\"'<>]+", re.I)


def _normalize_url(value: str) -> Optional[str]:
    value = html.unescape(unquote(value)).strip()
    match = WECHAT_URL_RE.search(value)
    if not match:
        return None
    parsed = urlparse(match.group(0))
    if parsed.hostname != "mp.weixin.qq.com" or not parsed.path.startswith("/s"):
        return None
    return match.group(0).rstrip(".,;:!?)）】]")


def _collect_urls(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_url(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


class PublicWechatDiscovery:
    """Best-effort discovery that never calls WeChat's appmsg list endpoint."""

    def __init__(self, db: Session):
        self.db = db
        self.pipeline = WechatPipeline(db)

    async def discover(
        self,
        account: WechatAccount,
        start_date: date,
        end_date: date,
        seed_urls: list[str],
        max_articles: int,
        category_id: Optional[str],
    ) -> dict[str, Any]:
        candidates: list[str] = []
        sources: dict[str, int] = {"seed": 0, "seed_links": 0, "public_search": 0, "local": 0}

        seeds = _collect_urls(seed_urls)
        candidates.extend(seeds)
        sources["seed"] = len(seeds)

        local = self.db.query(Article).filter(
            Article.source_type == "wechat",
            Article.author == account.name,
            Article.published_at >= start_date,
            Article.published_at <= end_date,
        ).limit(max_articles).all()
        local_urls = _collect_urls(item.url for item in local)
        candidates.extend(local_urls)
        sources["local"] = len(local_urls)

        seed_links = await self._discover_from_seed_pages(seeds)
        candidates.extend(seed_links)
        sources["seed_links"] = len(seed_links)

        public_urls = await self._search_public_indexes(account.name, start_date, end_date, max_articles)
        candidates.extend(public_urls)
        sources["public_search"] = len(public_urls)

        candidates = _collect_urls(candidates)[: max(max_articles * 4, max_articles)]
        reviewed: list[dict[str, Any]] = []

        await self.pipeline.crawler.start()
        try:
            for index, url in enumerate(candidates):
                article = await self.pipeline.crawler.fetch_article(url)
                if not article:
                    reviewed.append({
                        "url": url,
                        "title": "",
                        "account_name": "",
                        "published_at": "",
                        "eligible": False,
                        "reason": self.pipeline.crawler.errors.get(url, "文章页面无法读取"),
                    })
                    continue
                published = self._parse_date(article.publish_time)
                actual_account = (article.source_name or article.author or "").strip()
                reason = ""
                if actual_account != account.name.strip():
                    reason = f"公众号不匹配：{actual_account or '未知'}"
                elif not published:
                    reason = "无法识别发布日期"
                elif published < start_date or published > end_date:
                    reason = f"发布日期 {published.isoformat()} 不在范围内"
                reviewed.append({
                    "url": url,
                    "title": article.title,
                    "account_name": actual_account,
                    "published_at": published.isoformat() if published else "",
                    "eligible": not reason,
                    "reason": reason or "符合公众号和日期范围",
                })
                if index + 1 < len(candidates):
                    await asyncio.sleep(1.5)
        finally:
            await self.pipeline.crawler.stop()

        eligible_count = sum(1 for item in reviewed if item["eligible"])
        return {
            "candidate_count": len(candidates),
            "eligible_count": eligible_count,
            "verified_count": 0,
            "rejected_count": len(reviewed) - eligible_count,
            "sources": sources,
            "candidates": reviewed,
            "results": [],
            "rejected": [item for item in reviewed if not item["eligible"]],
        }

    async def _discover_from_seed_pages(self, seed_urls: list[str]) -> list[str]:
        if not seed_urls:
            return []
        found: list[str] = []
        timeout = httpx.Timeout(15.0)
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            for url in seed_urls[:5]:
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    found.extend(tag.get("href", "") for tag in soup.select("a[href]"))
                    found.extend(WECHAT_URL_RE.findall(response.text))
                except Exception as exc:
                    logger.info("公开种子页面链接发现失败 %s: %s", url, exc)
        return _collect_urls(found)

    async def _search_public_indexes(
        self, account_name: str, start_date: date, end_date: date, max_articles: int
    ) -> list[str]:
        query = quote_plus(
            f'site:mp.weixin.qq.com/s "{account_name}" after:{start_date.isoformat()} before:{end_date.isoformat()}'
        )
        found: list[str] = []
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
            for offset in range(0, min(max_articles * 2, 30), 10):
                try:
                    response = await client.get(f"https://www.bing.com/search?q={query}&first={offset + 1}")
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "html.parser")
                    found.extend(tag.get("href", "") for tag in soup.select("li.b_algo h2 a[href], a[href]"))
                    found.extend(WECHAT_URL_RE.findall(response.text))
                except Exception as exc:
                    logger.info("公开搜索发现失败: %s", exc)
                    break
                await asyncio.sleep(1)
        return _collect_urls(found)

    @staticmethod
    def _parse_date(value: str) -> Optional[date]:
        if not value:
            return None
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%Y年%m月%d日"):
            try:
                return datetime.strptime(value.strip(), fmt).date()
            except ValueError:
                continue
        match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", value)
        return date(*map(int, match.groups())) if match else None


async def run_public_discovery_job(
    job_id: str,
    db: Session,
    account: WechatAccount,
    start_date: date,
    end_date: date,
    seed_urls: list[str],
    max_articles: int,
    category_id: Optional[str],
) -> None:
    job = PUBLIC_DISCOVERY_JOBS[job_id]
    job.update({"status": "running", "started_at": datetime.utcnow().isoformat()})
    try:
        result = await PublicWechatDiscovery(db).discover(
            account, start_date, end_date, seed_urls, max_articles, category_id
        )
        job.update(result)
        job.update({
            "status": "completed",
            "success_count": 0,
            "failed_count": 0,
            "message": (
                f"公开来源发现完成：找到 {result['candidate_count']} 个候选，"
                f"其中 {result['eligible_count']} 篇符合自动筛选条件。请选择需要入库的文章。"
            ),
        })
    except Exception as exc:
        logger.exception("公开来源发现任务失败: %s", job_id)
        job.update({"status": "failed", "message": str(exc) or "公开来源发现失败"})
    finally:
        job["finished_at"] = datetime.utcnow().isoformat()


async def run_public_ingest_job(
    job_id: str,
    db: Session,
    urls: list[str],
    category_id: Optional[str],
) -> None:
    job = PUBLIC_DISCOVERY_JOBS[job_id]
    job.update({
        "status": "ingesting",
        "success_count": 0,
        "failed_count": 0,
        "message": f"正在将所选 {len(urls)} 篇文章入库",
    })
    try:
        results = await WechatPipeline(db).process_batch(urls, 1.5, category_id)
        successful = [item for item in results if item.get("success")]
        failed = [item for item in results if not item.get("success")]
        job.update({
            "status": "ingested" if successful else "failed",
            "results": results,
            "success_count": len(successful),
            "failed_count": len(failed),
            "verified_count": len(successful),
            "message": f"入库完成：成功 {len(successful)} 篇，失败 {len(failed)} 篇。",
        })
    except Exception as exc:
        logger.exception("公开来源候选文章入库失败: %s", job_id)
        job.update({"status": "failed", "message": str(exc) or "候选文章入库失败"})
    finally:
        job["finished_at"] = datetime.utcnow().isoformat()


def create_public_discovery_job() -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    job = {
        "job_id": job_id,
        "status": "pending",
        "candidate_count": 0,
        "eligible_count": 0,
        "verified_count": 0,
        "rejected_count": 0,
        "success_count": 0,
        "failed_count": 0,
        "sources": {},
        "candidates": [],
        "results": [],
        "rejected": [],
        "message": "公开来源发现任务等待执行",
        "created_at": datetime.utcnow().isoformat(),
    }
    PUBLIC_DISCOVERY_JOBS[job_id] = job
    return job
