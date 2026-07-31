# -*- coding: utf-8 -*-
"""
微信公众号爬取任务执行器

负责执行定时爬取任务，包括：
1. 获取公众号文章列表
2. 爬取文章内容
3. 保存到数据库
4. 触发知识图谱抽取
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.wechat import WechatAccount, WechatCrawlTask
from app.services.wechat.pipeline import WechatPipeline, get_wechat_pipeline

logger = logging.getLogger(__name__)


class WechatTaskExecutor:
    """微信公众号任务执行器"""

    def __init__(self, db: Session):
        self.db = db

    async def execute_task(self, task_id: str) -> Dict[str, Any]:
        """
        执行单个定时任务

        Args:
            task_id: 任务 ID

        Returns:
            执行结果
        """
        try:
            # 获取任务
            task = self.db.query(WechatCrawlTask).filter(WechatCrawlTask.id == task_id).first()
            if not task:
                return {"success": False, "error": "任务不存在"}

            # 获取公众号
            account = self.db.query(WechatAccount).filter(WechatAccount.id == task.account_id).first()
            if not account:
                return {"success": False, "error": "公众号不存在"}

            # 更新任务状态
            task.last_run_at = datetime.utcnow()
            self.db.commit()

            # 执行爬取
            result = await self._crawl_account(
                account_id=account.id,
                max_articles=task.max_articles
            )

            logger.info(f"任务执行完成: {task_id}, 结果: {result}")
            return result

        except Exception as e:
            logger.error(f"任务执行失败: {task_id}, 错误: {e}")
            return {"success": False, "error": str(e)}

    async def execute_account_crawl(
        self,
        account_id: str,
        max_articles: int = 10
    ) -> Dict[str, Any]:
        """
        执行公众号爬取

        Args:
            account_id: 公众号 ID
            max_articles: 最大爬取文章数

        Returns:
            执行结果
        """
        return await self._crawl_account(account_id, max_articles)

    async def _crawl_account(
        self,
        account_id: str,
        max_articles: int = 10
    ) -> Dict[str, Any]:
        """
        爬取公众号文章

        Args:
            account_id: 公众号 ID
            max_articles: 最大爬取文章数

        Returns:
            执行结果
        """
        try:
            # 获取公众号
            account = self.db.query(WechatAccount).filter(WechatAccount.id == account_id).first()
            if not account:
                return {"success": False, "error": "公众号不存在"}

            # 获取处理管道
            pipeline = get_wechat_pipeline(self.db)

            # TODO: 实际爬取公众号文章列表
            # 目前需要用户提供文章 URL，后续可以实现自动获取公众号文章列表
            # 这里先返回提示信息
            return {
                "success": True,
                "message": f"公众号 '{account.name}' 爬取任务已准备",
                "account_name": account.name,
                "note": "请提供文章 URL 进行爬取，或等待自动文章列表获取功能实现"
            }

        except Exception as e:
            logger.error(f"公众号爬取失败: {account_id}, 错误: {e}")
            return {"success": False, "error": str(e)}


def get_task_executor(db: Session = None) -> WechatTaskExecutor:
    """
    获取任务执行器实例

    Args:
        db: 数据库会话

    Returns:
        WechatTaskExecutor 实例
    """
    if db is None:
        db = next(get_db())
    return WechatTaskExecutor(db)
