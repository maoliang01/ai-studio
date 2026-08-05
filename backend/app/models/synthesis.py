"""知识综合文档模型。"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import DateTime, Index, Integer, JSON, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class KnowledgeSynthesis(Base):
    """多来源知识综合文档及其生命周期。"""

    __tablename__ = "knowledge_syntheses"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic: Mapped[str] = mapped_column(String(300), index=True)
    title: Mapped[str] = mapped_column(String(500), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    source_document_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    source_claim_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    iteration: Mapped[int] = mapped_column(Integer, default=1)
    parent_synthesis_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    model_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(80), default="knowledge_synthesis:v1")
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    __table_args__ = (
        Index("idx_knowledge_syntheses_topic_status", "topic", "status"),
    )
