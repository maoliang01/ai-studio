"""
知识图谱相关 Pydantic Schema 定义

包括：
- 知识点 (KnowledgePoint)
- 知识关联 (Association)
- 自增强循环结果 (SelfEnhancementResult)
- 统计信息 (EnhancementStats)
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class KnowledgePointSchema(BaseModel):
    """知识点"""
    id: str
    article_id: str
    title: str
    content: str
    category: str = Field(
        ...,
        description="知识点类型: concept(概念)/argument(观点)/fact(事实)/method(方法)"
    )
    confidence: float = Field(
        ge=0,
        le=1,
        description="置信度，0-1 之间"
    )
    keywords: List[str] = Field(default_factory=list, description="关键词列表")
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "kp_article1_0",
                "article_id": "article1",
                "title": "人工智能定义",
                "content": "人工智能是计算机科学的一个分支...",
                "category": "concept",
                "confidence": 0.9,
                "keywords": ["人工智能", "计算机科学", "智能"]
            }
        }


class AssociationSchema(BaseModel):
    """知识点关联"""
    id: str
    source_id: str = Field(..., description="源知识点 ID")
    target_id: str = Field(..., description="目标知识点 ID")
    relation_type: str = Field(
        ...,
        description="关系类型: related_to/supports/causes/part_of/contradicts"
    )
    strength: float = Field(
        ge=0,
        le=1,
        description="关联强度，0-1 之间"
    )
    evidence: str = Field(default="", description="关联证据")
    created_at: datetime = Field(default_factory=datetime.now)

    class Config:
        json_schema_extra = {
            "example": {
                "id": "assoc_kp0_kp1",
                "source_id": "kp_article1_0",
                "target_id": "kp_article1_1",
                "relation_type": "related_to",
                "strength": 0.8,
                "evidence": "关键词重叠: {'人工智能', '深度学习'}"
            }
        }


class SelfEnhancementResultSchema(BaseModel):
    """自增强循环结果"""
    enhancement_id: str
    article_id: str
    status: str = Field(
        ...,
        description="处理状态: pending/processing/completed/failed"
    )
    progress: int = Field(ge=0, le=100, default=0, description="处理进度 0-100")
    knowledge_points_count: int = Field(default=0, description="提取的知识点数量")
    associations_count: int = Field(default=0, description="发现的关联数量")
    summary: Optional[str] = Field(default=None, description="生成的总结")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None

    class Config:
        json_schema_extra = {
            "example": {
                "enhancement_id": "enh_article1_1234567890",
                "article_id": "article1",
                "status": "completed",
                "progress": 100,
                "knowledge_points_count": 8,
                "associations_count": 12,
                "summary": "本文提取了 8 个知识点..."
            }
        }


class EnhancementStatsSchema(BaseModel):
    """增强统计"""
    total_articles_processed: int = Field(default=0, description="已处理文章数")
    total_knowledge_points: int = Field(default=0, description="知识点总数")
    total_associations: int = Field(default=0, description="关联总数")
    average_points_per_article: float = Field(default=0, description="平均知识点/文章")
    average_associations_per_point: float = Field(default=0, description="平均关联/知识点")
    last_processed_at: Optional[datetime] = Field(default=None, description="最后处理时间")


class ProcessArticleRequest(BaseModel):
    """处理文章请求"""
    article_id: str = Field(..., description="文章 ID")
    article_content: Optional[str] = Field(default=None, description="文章内容（可选，如果不提供则从数据库获取）")


class KnowledgePointListResponse(BaseModel):
    """知识点列表响应"""
    knowledge_points: List[KnowledgePointSchema]
    total: int


class AssociationListResponse(BaseModel):
    """关联列表响应"""
    associations: List[AssociationSchema]
    total: int


class TrendPredictionRequest(BaseModel):
    """趋势预测请求"""
    topic: str = Field(..., description="预测主题")
    time_range: int = Field(default=30, ge=1, le=365, description="预测天数")
    prediction_type: str = Field(
        default="general",
        description="预测类型: general/technology/sentiment/knowledge"
    )


class TrendPredictionResponse(BaseModel):
    """趋势预测响应"""
    topic: str
    trend: str = Field(..., description="趋势方向: up/down/stable")
    confidence: float = Field(ge=0, le=1, description="置信度")
    factors: List[dict] = Field(default_factory=list, description="影响因素")
    timeline: List[dict] = Field(default_factory=list, description="时间线预测")
    prediction_type: str
    generated_at: datetime = Field(default_factory=datetime.now)
