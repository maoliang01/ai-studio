"""趋势预测记录与反馈模型。"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import DateTime, Float, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PredictionRecord(Base):
    """保存预测快照，便于回放、人工反馈和后续命中率评估。"""

    __tablename__ = "prediction_records"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    topic: Mapped[str] = mapped_column(String(300), index=True)
    prediction_type: Mapped[str] = mapped_column(String(50), default="general")
    time_range: Mapped[int] = mapped_column(Integer, default=30)
    trend: Mapped[str] = mapped_column(String(20), default="stable")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    factors: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    timeline: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    knowledge_basis: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    interpretation: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_trend: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    accuracy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    evaluated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_prediction_records_topic_created", "topic", "created_at"),
    )
