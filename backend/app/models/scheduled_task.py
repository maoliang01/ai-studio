"""
定时任务相关的数据模型

包含：定时任务配置、爬取历史记录
"""
import uuid
import json
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    Column, String, Text, Integer, Boolean, DateTime,
    ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.orm import relationship, Mapped, mapped_column
import enum

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.article import ScrapeSource


class TaskStatus(str, enum.Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 待执行
    RUNNING = "running"      # 执行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    CANCELLED = "cancelled"  # 已取消


class ScheduledTask(Base):
    """定时任务配置模型"""

    __tablename__ = "scheduled_tasks"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 关联的爬取源ID列表（JSON 数组，兼容旧数据保留 source_id）
    source_ids: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON 数组
    # 兼容旧字段：单个爬取源ID
    source_id: Mapped[Optional[str]] = mapped_column(
        String(50), ForeignKey("scrape_sources.id"), nullable=True
    )
    # 自定义URL（如果为空则使用关联爬取源的URL）
    custom_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # 爬取时间（cron 表达式，简化版：HH:MM 格式存储）
    schedule_time: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g., "09:00"
    # 爬取范围：往前追溯的时间范围，如 "1d"(前一天) "7d"(前一周) "30d"(前一月)
    scrape_range: Mapped[str] = mapped_column(String(10), default="1d")
    # 是否启用
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    # 上次执行时间
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 下次执行时间
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # 关联关系
    source: Mapped[Optional["ScrapeSource"]] = relationship(
        "ScrapeSource", back_populates="scheduled_tasks"
    )
    histories: Mapped[List["ScrapeHistory"]] = relationship(
        "ScrapeHistory", back_populates="task", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_tasks_source", "source_id"),
        Index("idx_tasks_source_ids", "source_ids"),
        Index("idx_tasks_enabled", "is_enabled"),
        Index("idx_tasks_next_run", "next_run_at"),
    )

    def get_source_ids_list(self) -> List[str]:
        """获取源ID列表"""
        if self.source_ids:
            try:
                return json.loads(self.source_ids)
            except (json.JSONDecodeError, TypeError):
                pass
        if self.source_id:
            return [self.source_id]
        return []

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "source_id": self.source_id,
            "source_ids": self.get_source_ids_list(),
            "custom_url": self.custom_url,
            "schedule_time": self.schedule_time,
            "scrape_range": self.scrape_range,
            "is_enabled": self.is_enabled,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "next_run_at": self.next_run_at.isoformat() if self.next_run_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScrapeHistory(Base):
    """爬取历史记录模型"""

    __tablename__ = "scrape_histories"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    # 关联的任务ID
    task_id: Mapped[Optional[str]] = mapped_column(
        String(36), ForeignKey("scheduled_tasks.id"), nullable=True
    )
    # 爬取的URL
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # 文章标题（爬取成功后保存）
    article_title: Mapped[Optional[str]] = mapped_column(String(500))
    # 关联的文章ID
    article_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    # 执行状态
    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    # 错误信息
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    # 开始时间
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # 结束时间
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # 爬取的文章数量
    articles_count: Mapped[int] = mapped_column(Integer, default=0)
    # 创建时间
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # 关联关系
    task: Mapped[Optional["ScheduledTask"]] = relationship(
        "ScheduledTask", back_populates="histories"
    )

    __table_args__ = (
        Index("idx_history_task", "task_id"),
        Index("idx_history_status", "status"),
        Index("idx_history_started", "started_at"),
        Index("idx_history_created", "created_at"),
    )

    def to_dict(self) -> dict:
        """转换为字典"""
        duration = None
        if self.started_at and self.finished_at:
            duration = (self.finished_at - self.started_at).total_seconds()

        return {
            "id": self.id,
            "task_id": self.task_id,
            "url": self.url,
            "article_title": self.article_title,
            "article_id": self.article_id,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration": duration,
            "articles_count": self.articles_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }