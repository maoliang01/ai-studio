"""
定时任务调度器

使用 APScheduler 实现定时爬取任务
"""
import asyncio
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.database import get_db
from app.models.scheduled_task import ScheduledTask, ScrapeHistory, TaskStatus
from app.models.wechat import WechatCrawlTask

logger = logging.getLogger("scheduler")


def create_scheduler() -> BackgroundScheduler:
    """创建调度器"""
    scheduler = BackgroundScheduler(
        timezone="Asia/Shanghai",
        job_defaults={
            'max_instances': 1,  # 同一任务最多1个实例，防止重复执行
            'coalesce': False,   # 不合并错过的执行
            'misfire_grace_time': 60,  # 错过触发时间60秒内仍执行
        }
    )
    return scheduler


def cleanup_stuck_tasks(max_runtime_minutes: int = 60):
    """清理运行时间过长的卡住任务"""
    from app.core.database import get_session_local
    SessionLocal = get_session_local()
    session = SessionLocal()
    try:
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(minutes=max_runtime_minutes)

        # 查找运行时间超过 max_runtime_minutes 的任务
        stuck_tasks = session.query(ScrapeHistory).filter(
            ScrapeHistory.status == TaskStatus.RUNNING.value,
            ScrapeHistory.started_at < cutoff
        ).all()

        if stuck_tasks:
            logger.warning(f"发现 {len(stuck_tasks)} 个卡住的任务，正在清理...")
            for task in stuck_tasks:
                task.status = TaskStatus.FAILED.value
                task.finished_at = datetime.utcnow()
                task.error_message = f"任务超时（运行超过 {max_runtime_minutes} 分钟）自动终止"
            session.commit()
            logger.warning(f"已清理 {len(stuck_tasks)} 个卡住任务")

    except Exception as e:
        logger.error(f"清理卡住任务失败: {e}")
    finally:
        session.close()


def run_wechat_crawl_task(task_id: str):
    """执行微信公众号爬取任务"""
    logger.info(f"⏰ [微信爬取] 开始执行任务: {task_id}")

    # 创建新的数据库会话确保线程安全
    from app.core.database import get_session_local

    db = get_session_local()()
    try:
        task = db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        # 检查任务是否在最近10分钟内执行过（防止重复执行）
        if task.last_run_at:
            from datetime import timedelta
            if datetime.utcnow() - task.last_run_at < timedelta(minutes=10):
                logger.warning(f"微信任务 '{task_id}' 刚执行过，跳过本次执行")
                return

        start_time = datetime.utcnow()

        logger.info(f"⏰ [微信爬取] 开始爬取公众号...")

        # 执行爬取
        try:
            import asyncio
            from app.services.wechat.task_executor import WechatTaskExecutor

            # 创建新的事件循环用于线程中运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            executor = WechatTaskExecutor(db)
            result = loop.run_until_complete(executor.execute_task(task_id))
            loop.close()

            # 更新任务状态
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            task.last_run_at = datetime.utcnow()
            task.next_run_at = _calculate_next_run(task.schedule_time)
            db.commit()

            logger.info(f"✅ [微信爬取] 任务执行完成！耗时 {duration:.1f}秒")

        except Exception as e:
            logger.error(f"❌ [微信爬取] 任务执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            db.commit()

    except Exception as e:
        logger.error(f"执行微信任务 {task_id} 时出错: {e}")
    finally:
        db.close()


def run_scheduled_task(task_id: str):
    """执行单个定时任务"""
    logger.info(f"⏰ [定时执行] 开始执行任务: {task_id}")

    # 创建新的数据库会话确保线程安全
    from app.core.database import get_session_local

    db = get_session_local()()
    try:
        task = db.query(ScheduledTask).filter(ScheduledTask.id == task_id).first()
        if not task:
            logger.error(f"任务不存在: {task_id}")
            return

        # 检查是否有同任务正在运行（防止重复执行）
        running_count = db.query(ScrapeHistory).filter(
            ScrapeHistory.task_id == task_id,
            ScrapeHistory.status == TaskStatus.RUNNING.value
        ).count()

        if running_count > 0:
            logger.warning(f"任务 '{task.name}' 已有实例在运行，跳过本次执行")
            return

        start_time = datetime.utcnow()

        # 创建历史记录
        history = ScrapeHistory(
            task_id=task_id,
            url="调度执行",
            status=TaskStatus.RUNNING.value,
            started_at=start_time,
        )
        db.add(history)
        db.flush()

        logger.info(f"⏰ [定时执行] 任务 '{task.name}' 开始爬取...")

        # 执行爬取
        try:
            # 获取要爬取的URL列表
            from sqlalchemy import text
            from app.services.scraper import get_scraper, ScrapeOptions
            from app.models.article import ScrapeSource
            import asyncio

            source_ids = task.get_source_ids_list()
            urls = []
            source_id = source_ids[0] if source_ids else None

            # 获取爬取源的 category_id
            category_id = None
            if source_ids:
                source = db.query(ScrapeSource).filter(ScrapeSource.id == source_ids[0]).first()
                if source:
                    category_id = source.category_id
                    source_id = source.id

            if task.custom_url:
                urls = [task.custom_url]
            else:
                for sid in source_ids:
                    result = db.execute(text(f"SELECT url FROM scrape_sources WHERE id = '{sid}'")).fetchone()
                    if result:
                        urls.append(result[0])

            total_articles = 0
            scraper = get_scraper()

            # 使用与正常网页爬取 /api/scrape 相同的选项
            options = ScrapeOptions()  # 默认值：extract_content=True, fetch_html=False, preserve_format=False, max_depth=0

            # 任务最大执行时间（秒），默认 10 分钟，防止任务卡住
            TASK_MAX_RUNTIME = 600  # 10 分钟

            # 创建新的事件循环用于线程中运行
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # 保存每个爬取的文章信息
            scraped_articles = []
            task_exceeded = False

            for url in urls:
                # 检查是否超过最大执行时间
                elapsed = (datetime.utcnow() - start_time).total_seconds()
                if elapsed > TASK_MAX_RUNTIME:
                    logger.warning(f"任务 '{task.name}' 执行时间超过 {TASK_MAX_RUNTIME} 秒，强制结束")
                    task_exceeded = True
                    break

                logger.info(f"深度爬取 URL: {url}")
                try:
                    # 使用 asyncio.wait_for 为每次爬取添加超时保护（120秒）
                    async def _scrape_with_timeout():
                        return await asyncio.wait_for(
                            scraper.deep_scrape(
                                url=url,
                                options=options,
                                max_articles=20,
                                date_range=task.scrape_range,
                                scrape_level="deep"
                            ),
                            timeout=120  # 单个 URL 最多 2 分钟
                        )

                    list_page, article_results = loop.run_until_complete(_scrape_with_timeout())
                    logger.info(f"  列表页: {list_page.title}, 识别到 {len(article_results)} 篇文章")

                    # 保存每篇文章到数据库
                    for result in article_results:
                        if result.content and result.word_count > 50:
                            saved, article_id = scraper.save_to_database(
                                result, category_id=category_id, source_id=source_id
                            )
                            if saved:
                                total_articles += 1
                                title = result.title or "无标题"
                                scraped_articles.append(title)
                                logger.info(f"      ✓ 已保存: {title[:50]}")
                        else:
                            logger.info(f"    内容不足，跳过: {result.url}")

                except asyncio.TimeoutError:
                    logger.error(f"  爬取超时（120秒）: {url}")
                except Exception as url_error:
                    logger.error(f"  爬取失败: {url_error}")

            loop.close()

            # 如果是任务超时导致提前结束，记录警告但不标记失败（已有部分文章爬取）
            if task_exceeded:
                history.article_title = "\n".join([
                    f"{i+1}. {title[:40]}" for i, title in enumerate(scraped_articles[:10])
                ]) + (f"\n... 还有 {len(scraped_articles) - 10} 篇（任务超时提前结束）" if len(scraped_articles) > 10 else "")
                logger.warning(f"任务 '{task.name}' 因超时提前结束，已保存 {len(scraped_articles)} 篇文章")

            # 更新历史记录 - 使用列表格式显示所有文章标题
            end_time = datetime.utcnow()
            duration = (end_time - start_time).total_seconds()

            if scraped_articles:
                # 格式化为列表
                article_list = []
                for i, title in enumerate(scraped_articles[:10], 1):  # 最多显示10个
                    article_list.append(f"{i}. {title[:40]}")
                if len(scraped_articles) > 10:
                    article_list.append(f"... 还有 {len(scraped_articles) - 10} 篇")

                history.article_title = "\n".join(article_list)
            else:
                history.article_title = "无文章"

            history.status = TaskStatus.SUCCESS.value
            history.started_at = start_time
            history.finished_at = end_time
            history.duration = duration
            history.articles_count = total_articles
            history.url = ", ".join(urls[:3]) + ("..." if len(urls) > 3 else "")
            task.last_run_at = datetime.utcnow()
            task.next_run_at = _calculate_next_run(task.schedule_time)
            db.commit()

            logger.info(f"✅ [定时执行] 任务 '{task.name}' 完成！保存了 {total_articles} 篇文章，耗时 {duration:.1f}秒")

        except Exception as e:
            logger.error(f"❌ [定时执行] 任务 '{task.name}' 执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            history.status = TaskStatus.FAILED.value
            history.error_message = str(e)
            history.started_at = start_time
            history.finished_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        logger.error(f"执行任务 {task_id} 时出错: {e}")
    finally:
        db.close()


def _calculate_next_run(schedule_time: str) -> datetime:
    """计算下次执行时间"""
    now = datetime.now()
    hour, minute = map(int, schedule_time.split(":"))
    next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if next_run <= now:
        next_run = next_run.replace(day=next_run.day + 1)
    return next_run


def sync_scheduler_tasks(scheduler: BackgroundScheduler):
    """同步调度器中的任务（从数据库加载）"""
    from app.core.database import get_session_local

    db = get_session_local()()
    try:
        # 获取所有启用的任务
        tasks = db.query(ScheduledTask).filter(ScheduledTask.is_enabled == True).all()

        # 获取所有启用的微信爬取任务
        wechat_tasks = db.query(WechatCrawlTask).filter(WechatCrawlTask.is_enabled == True).all()

        # 清空现有任务（保留调度器运行）
        scheduler.remove_all_jobs()

        # 添加普通定时任务
        for task in tasks:
            job_id = f"task_{task.id}"
            hour, minute = map(int, task.schedule_time.split(":"))

            scheduler.add_job(
                func=run_scheduled_task,
                trigger=CronTrigger(hour=hour, minute=minute, timezone="Asia/Shanghai"),
                id=job_id,
                args=[task.id],
                replace_existing=True,
                name=f"定时爬取: {task.name}",
            )
            logger.info(f"📅 [调度器] 添加任务: '{task.name}' → 每日 {task.schedule_time}")

        # 添加微信爬取任务
        for task in wechat_tasks:
            job_id = f"wechat_{task.id}"
            if task.schedule_time:
                hour, minute = map(int, task.schedule_time.split(":"))

                # 根据 schedule_type 设置触发器
                if task.schedule_type == "daily":
                    trigger = CronTrigger(hour=hour, minute=minute, timezone="Asia/Shanghai")
                elif task.schedule_type == "weekly":
                    trigger = CronTrigger(day_of_week="mon", hour=hour, minute=minute, timezone="Asia/Shanghai")
                elif task.schedule_type == "monthly":
                    trigger = CronTrigger(day=1, hour=hour, minute=minute, timezone="Asia/Shanghai")
                else:
                    trigger = CronTrigger(hour=hour, minute=minute, timezone="Asia/Shanghai")

                scheduler.add_job(
                    func=run_wechat_crawl_task,
                    trigger=trigger,
                    id=job_id,
                    args=[task.id],
                    replace_existing=True,
                    name=f"微信爬取: {task.account_id}",
                )
                logger.info(f"📅 [调度器] 添加微信任务: {task.account_id} → {task.schedule_type} {task.schedule_time}")

        logger.info(f"调度器同步完成，共 {len(tasks)} 个普通任务，{len(wechat_tasks)} 个微信任务")

    except Exception as e:
        logger.error(f"同步调度任务失败: {e}")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """启动调度器"""
    scheduler = create_scheduler()

    # 启动时先清理卡住的任务（运行超过60分钟）
    logger.info("启动时检查并清理卡住的任务...")
    cleanup_stuck_tasks(max_runtime_minutes=60)

    # 初始同步
    sync_scheduler_tasks(scheduler)

    # 每10分钟检查并清理卡住的任务
    scheduler.add_job(
        func=cleanup_stuck_tasks,
        trigger=CronTrigger(minute="*/10", timezone="Asia/Shanghai"),
        id="cleanup_stuck_tasks",
        args=[60],  # 超时60分钟
        replace_existing=True,
        max_instances=1,
        name="清理卡住任务",
    )
    logger.info("卡住任务自动清理任务已注册（每10分钟检查，运行超过60分钟的任务将被清理）")

    # 每小时重新同步一次（处理新增/修改的任务）
    scheduler.add_job(
        func=sync_scheduler_tasks,
        trigger=CronTrigger(minute=0, timezone="Asia/Shanghai"),
        id="sync_tasks",
        args=[scheduler],
        replace_existing=True,
        name="同步定时任务",
    )

    scheduler.start()
    logger.info("定时任务调度器已启动")

    return scheduler


# ============ KG 对账定时任务(可选,默认关闭) ============

async def kg_reconcile_task():
    """定时对账任务:每 N 分钟跑一次,apply=False(只报告不修)"""
    from app.core.database import get_session_local
    from app.services.kg_sync import reconcile
    SessionLocal = get_session_local()
    session = SessionLocal()
    try:
        result = await reconcile(apply=False, db=session)
        logger.info(
            f"KG 对账报告: sqlite={result['sqlite_count']} "
            f"kg={result['kg_count']} "
            f"missing={len(result['missing_in_kg'])} "
            f"orphan={len(result['orphan_in_kg'])} "
            f"dirty={len(result['dirty_in_kg'])}"
        )
        if result['missing_in_kg'] or result['orphan_in_kg'] or result['dirty_in_kg']:
            logger.warning(f"KG 漂移检测: {result}")
    finally:
        session.close()


def register_kg_reconcile_job(scheduler, interval_minutes: int = 30):
    """注册定时对账任务(默认 30 分钟一次)

    当 interval_minutes <= 0 时不注册,等价于关闭。
    """
    if interval_minutes <= 0:
        logger.info("KG 定时对账未启用(interval_minutes <= 0)")
        return
    scheduler.add_job(
        kg_reconcile_task,
        "interval",
        minutes=interval_minutes,
        id="kg_reconcile",
        replace_existing=True,
        max_instances=1
    )
    logger.info(f"KG 定时对账任务已注册,间隔 {interval_minutes} 分钟")


# 全局调度器实例
_scheduler: BackgroundScheduler | None = None


def get_scheduler() -> BackgroundScheduler | None:
    """获取调度器实例"""
    return _scheduler


def init_scheduler() -> BackgroundScheduler:
    """初始化调度器（供应用启动时调用）"""
    global _scheduler
    if _scheduler is None:
        _scheduler = start_scheduler()
    return _scheduler


def shutdown_scheduler():
    """关闭调度器"""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
        logger.info("定时任务调度器已关闭")