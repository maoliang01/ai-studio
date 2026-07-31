# -*- coding: utf-8 -*-
"""
微信公众号相关的数据模型

包含：公众号账号、Cookie、定时任务等表的定义
"""

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.core.database import Base


class WechatAccount(Base):
    """微信公众号账号模型"""

    __tablename__ = "wechat_accounts"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    wechat_id: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    fakeid: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_crawled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    article_count: Mapped[int] = mapped_column(Integer, default=0)
    min_crawl_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_discovery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_discovery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_discovery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rate_limit_count: Mapped[int] = mapped_column(Integer, default=0)
    discovery_cache: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关联关系
    crawl_tasks: Mapped[List["WechatCrawlTask"]] = relationship(
        "WechatCrawlTask", back_populates="account"
    )

    __table_args__ = (
        Index("idx_wechat_accounts_enabled", "is_enabled"),
        Index("idx_wechat_accounts_wechat_id", "wechat_id"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "wechat_id": self.wechat_id,
            "fakeid": self.fakeid,
            "description": self.description,
            "is_enabled": self.is_enabled,
            "last_crawled_at": self.last_crawled_at.isoformat() if self.last_crawled_at else None,
            "article_count": self.article_count,
            "min_crawl_interval_minutes": self.min_crawl_interval_minutes,
            "last_discovery_at": f"{self.last_discovery_at.isoformat()}Z" if self.last_discovery_at else None,
            "next_discovery_at": f"{self.next_discovery_at.isoformat()}Z" if self.next_discovery_at else None,
            "last_discovery_status": self.last_discovery_status,
            "rate_limit_count": self.rate_limit_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WechatCookie(Base):
    """微信公众号 Cookie 模型"""

    __tablename__ = "wechat_cookies"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cookie_data: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_discovery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_discovery_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_discovery_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    rate_limit_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_wechat_cookies_active", "is_active"),
        Index("idx_wechat_cookies_expires", "expires_at"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "is_active": self.is_active,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "last_discovery_at": f"{self.last_discovery_at.isoformat()}Z" if self.last_discovery_at else None,
            "next_discovery_at": f"{self.next_discovery_at.isoformat()}Z" if self.next_discovery_at else None,
            "last_discovery_status": self.last_discovery_status,
            "rate_limit_count": self.rate_limit_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class WechatCrawlTask(Base):
    """微信公众号爬取任务模型"""

    __tablename__ = "wechat_crawl_tasks"

    id: Mapped[str] = mapped_column(
        String(50), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    account_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("wechat_accounts.id")
    )
    schedule_type: Mapped[str] = mapped_column(String(50), nullable=False)  # daily/weekly/monthly
    schedule_time: Mapped[Optional[str]] = mapped_column(String(20))  # HH:MM
    max_articles: Mapped[int] = mapped_column(Integer, default=10)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关联关系
    account: Mapped["WechatAccount"] = relationship("WechatAccount", back_populates="crawl_tasks")

    __table_args__ = (
        Index("idx_wechat_tasks_account", "account_id"),
        Index("idx_wechat_tasks_enabled", "is_enabled"),
        Index("idx_wechat_tasks_next_run", "next_run_at"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "schedule_type": self.schedule_type,
            "schedule_time": self.schedule_time,
            "max_articles": self.max_articles,
            "is_enabled": self.is_enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
