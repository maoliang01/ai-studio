"""
知识自增强循环单元测试

测试核心功能：
- 文章预处理
- 知识点提取（规则方式）
- 关联发现
- 总结生成
- 趋势预测
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.services.kg.self_enhancement import (
    KnowledgeSelfEnhancement,
    KnowledgePoint,
    Association,
    SelfEnhancementResult
)
from app.services.kg.prediction import TrendPredictionEngine, PredictionResult
from app.services.kg.event_listener import KnowledgeEventListener


class TestKnowledgeSelfEnhancement:
    """知识自增强循环测试"""

    @pytest.fixture
    def mock_kg_service(self):
        """模拟知识图谱服务"""
        service = AsyncMock()
        service.create_entity = AsyncMock()
        service.create_relationship = AsyncMock()
        return service

    @pytest.fixture
    def enhancement_service(self, mock_kg_service):
        """创建增强服务实例"""
        return KnowledgeSelfEnhancement(mock_kg_service, llm_client=None)

    def test_preprocess_article(self, enhancement_service):
        """测试文章预处理"""
        # 测试 HTML 标签移除
        content = "<p>测试内容</p><br/>"
        result = enhancement_service._preprocess_article(content)
        assert "<p>" not in result
        assert "测试内容" in result

        # 测试空白合并
        content = "测试    内容"
        result = enhancement_service._preprocess_article(content)
        assert "    " not in result

        # 测试空内容
        result = enhancement_service._preprocess_article("")
        assert result == ""

        result = enhancement_service._preprocess_article(None)
        assert result == ""

    @pytest.mark.skipif(
        not pytest.importorskip("jieba"),
        reason="jieba not installed"
    )
    def test_rule_based_extract_points(self, enhancement_service):
        """测试基于规则的知识点提取"""
        content = "人工智能是一种定义。机器学习是重要的概念。深度学习是人工智能的子领域。"
        points = enhancement_service._rule_based_extract_points(content)

        assert len(points) > 0
        assert all('title' in p for p in points)
        assert all('content' in p for p in points)
        assert all('category' in p for p in points)
        assert all('confidence' in p for p in points)

    @pytest.mark.skipif(
        not pytest.importorskip("jieba"),
        reason="jieba not installed"
    )
    def test_extract_keywords(self, enhancement_service):
        """测试关键词提取"""
        text = "人工智能技术正在快速发展"
        keywords = enhancement_service._extract_keywords(text)

        assert isinstance(keywords, list)
        assert len(keywords) <= 5

    def test_calculate_association(self, enhancement_service):
        """测试关联计算"""
        point_a = KnowledgePoint(
            id="kp_1",
            article_id="art_1",
            title="知识点A",
            content="内容A",
            category="concept",
            confidence=0.8,
            keywords=["人工智能", "机器学习"]
        )

        point_b = KnowledgePoint(
            id="kp_2",
            article_id="art_1",
            title="知识点B",
            content="内容B",
            category="concept",
            confidence=0.7,
            keywords=["机器学习", "深度学习"]
        )

        association = enhancement_service._calculate_association(point_a, point_b)

        assert association is not None
        assert association.strength > 0
        assert association.source_id == "kp_1"
        assert association.target_id == "kp_2"

    def test_calculate_association_no_keywords(self, enhancement_service):
        """测试无关键词时的关联计算"""
        point_a = KnowledgePoint(
            id="kp_1",
            article_id="art_1",
            title="知识点A",
            content="内容A",
            category="concept",
            confidence=0.8,
            keywords=[]
        )

        point_b = KnowledgePoint(
            id="kp_2",
            article_id="art_1",
            title="知识点B",
            content="内容B",
            category="concept",
            confidence=0.7,
            keywords=["机器学习"]
        )

        association = enhancement_service._calculate_association(point_a, point_b)
        assert association is None

    def test_rule_based_summary(self, enhancement_service):
        """测试基于规则的总结生成"""
        points = [
            KnowledgePoint(
                id="kp_1",
                article_id="art_1",
                title="知识点1",
                content="内容1",
                category="concept",
                confidence=0.8,
                keywords=[]
            ),
            KnowledgePoint(
                id="kp_2",
                article_id="art_1",
                title="知识点2",
                content="内容2",
                category="argument",
                confidence=0.7,
                keywords=[]
            )
        ]

        associations = [
            Association(
                id="assoc_1",
                source_id="kp_1",
                target_id="kp_2",
                relation_type="related_to",
                strength=0.6
            )
        ]

        summary = enhancement_service._rule_based_summary(points, associations)

        assert "2 个知识点" in summary
        assert "概念" in summary
        assert "观点" in summary
        assert "1 个知识关联" in summary

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not pytest.importorskip("jieba"),
        reason="jieba not installed"
    )
    async def test_process_new_article(self, enhancement_service):
        """测试处理新文章"""
        article_id = "test_article_1"
        content = "人工智能是一种定义。机器学习是重要的概念。"

        result = await enhancement_service.process_new_article(article_id, content)

        assert isinstance(result, SelfEnhancementResult)
        assert result.article_id == article_id
        assert result.status == 'completed'
        assert result.knowledge_points_count > 0
        assert result.progress == 100
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_process_new_article_updates_existing(self, enhancement_service):
        """测试更新已处理的文章"""
        article_id = "test_article_1"
        content = "第一次处理的内容"

        result1 = await enhancement_service.process_new_article(article_id, content)
        enhancement_id1 = result1.enhancement_id

        # 再次处理同一文章
        content2 = "第二次处理的内容"
        result2 = await enhancement_service.process_new_article(article_id, content2)

        # 应该更新现有记录
        assert result2.enhancement_id == enhancement_id1
        assert result2.status == 'completed'

    def test_get_processing_status(self, enhancement_service):
        """测试获取处理状态"""
        # 不存在的任务
        result = enhancement_service.get_processing_status("nonexistent")
        assert result is None


class TestTrendPrediction:
    """趋势预测测试"""

    @pytest.fixture
    def mock_kg_service(self):
        """模拟知识图谱服务"""
        service = AsyncMock()
        service.search_entities = AsyncMock(return_value=[])
        service.get_relationships = AsyncMock(return_value=[])
        return service

    @pytest.fixture
    def prediction_engine(self, mock_kg_service):
        """创建预测引擎实例"""
        return TrendPredictionEngine(mock_kg_service)

    @pytest.mark.asyncio
    async def test_predict_trend(self, prediction_engine):
        """测试趋势预测"""
        result = await prediction_engine.predict_trend("人工智能", time_range=30)

        assert isinstance(result, PredictionResult)
        assert result.topic == "人工智能"
        assert result.trend in ['up', 'down', 'stable']
        assert 0 <= result.confidence <= 1
        assert len(result.timeline) == 30
        assert result.prediction_type == 'general'

    @pytest.mark.asyncio
    async def test_predict_sentiment(self, prediction_engine):
        """测试舆情预测"""
        result = await prediction_engine.predict_sentiment("人工智能")

        assert result.prediction_type == 'sentiment'

    @pytest.mark.asyncio
    async def test_predict_technology(self, prediction_engine):
        """测试技术趋势预测"""
        result = await prediction_engine.predict_technology("人工智能")

        assert result.prediction_type == 'technology'

    def test_generate_timeline(self, prediction_engine):
        """测试时间线生成"""
        timeline = prediction_engine._generate_timeline('up', 7)

        assert len(timeline) == 7
        assert all('date' in t for t in timeline)
        assert all('predicted_value' in t for t in timeline)
        assert all('confidence_interval' in t for t in timeline)

    def test_generate_default_timeline(self, prediction_engine):
        """测试默认时间线生成"""
        timeline = prediction_engine._generate_default_timeline(5)

        assert len(timeline) == 5


class TestEventListener:
    """事件监听器测试"""

    @pytest.fixture
    def mock_enhancement_service(self):
        """模拟增强服务"""
        service = AsyncMock()
        service.process_new_article = AsyncMock()
        return service

    @pytest.fixture
    def event_listener(self, mock_enhancement_service):
        """创建事件监听器实例"""
        return KnowledgeEventListener(mock_enhancement_service)

    @pytest.mark.asyncio
    async def test_emit_article_created(self, event_listener, mock_enhancement_service):
        """测试文章创建事件"""
        await event_listener.emit('article_created', {
            'article_id': 'test_1',
            'content': '测试内容'
        })

        mock_enhancement_service.process_new_article.assert_called_once_with(
            'test_1', '测试内容'
        )

    @pytest.mark.asyncio
    async def test_emit_article_updated(self, event_listener, mock_enhancement_service):
        """测试文章更新事件"""
        await event_listener.emit('article_updated', {
            'article_id': 'test_1',
            'content': '更新内容'
        })

        mock_enhancement_service.process_new_article.assert_called_once_with(
            'test_1', '更新内容'
        )

    @pytest.mark.asyncio
    async def test_emit_unknown_event(self, event_listener):
        """测试未知事件"""
        # 不应抛出异常
        await event_listener.emit('unknown_event', {})

    @pytest.mark.asyncio
    async def test_emit_missing_data(self, event_listener, mock_enhancement_service):
        """测试缺少数据的事件"""
        await event_listener.emit('article_created', {})

        mock_enhancement_service.process_new_article.assert_not_called()

    def test_register_handler(self, event_listener):
        """测试注册自定义处理器"""
        handler = AsyncMock()
        event_listener.register_handler('custom_event', handler)

        assert 'custom_event' in event_listener.handlers
        assert handler in event_listener.handlers['custom_event']
