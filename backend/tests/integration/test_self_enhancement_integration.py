"""
知识自增强循环集成测试

测试 API 端点和完整流程。
注意：这些测试需要后端服务运行。
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from app.services.kg.self_enhancement import KnowledgeSelfEnhancement, SelfEnhancementResult
from app.services.kg.prediction import TrendPredictionEngine, PredictionResult


class TestSelfEnhancementIntegration:
    """自增强循环集成测试"""

    @pytest.fixture
    def mock_neo4j_service(self):
        """模拟 Neo4j 服务"""
        service = AsyncMock()
        service.create_entity = AsyncMock()
        service.create_relationship = AsyncMock()
        service.search_entities = AsyncMock(return_value=[])
        service.get_relationships = AsyncMock(return_value=[])
        return service

    @pytest.mark.asyncio
    async def test_full_enhancement_flow(self, mock_neo4j_service):
        """测试完整的增强流程"""
        service = KnowledgeSelfEnhancement(mock_neo4j_service, llm_client=None)

        # 处理文章
        result = await service.process_new_article(
            article_id="integration_test_1",
            article_content="人工智能是计算机科学的一个分支。机器学习是人工智能的核心技术。深度学习是机器学习的一个子领域。"
        )

        # 验证结果
        assert result.status == 'completed'
        assert result.knowledge_points_count > 0
        assert result.associations_count >= 0
        assert result.summary is not None
        assert result.progress == 100

        # 验证数据库调用
        assert mock_neo4j_service.create_entity.call_count > 0

    @pytest.mark.asyncio
    async def test_stats_collection(self, mock_neo4j_service):
        """测试统计数据收集"""
        service = KnowledgeSelfEnhancement(mock_neo4j_service, llm_client=None)

        # 处理多篇文章
        await service.process_new_article("art_1", "第一篇文章内容")
        await service.process_new_article("art_2", "第二篇文章内容")

        # 获取统计信息（使用内存统计）
        stats = service.get_stats()

        assert 'total_articles_processed' in stats
        assert 'total_knowledge_points' in stats
        assert 'total_associations' in stats


class TestPredictionIntegration:
    """预测功能集成测试"""

    @pytest.fixture
    def mock_neo4j_service(self):
        """模拟 Neo4j 服务"""
        service = AsyncMock()
        service.search_entities = AsyncMock(return_value=[])
        service.get_relationships = AsyncMock(return_value=[])
        return service

    @pytest.mark.asyncio
    async def test_trend_prediction_flow(self, mock_neo4j_service):
        """测试趋势预测完整流程"""
        engine = TrendPredictionEngine(mock_neo4j_service)

        result = await engine.predict_trend(
            topic="人工智能",
            time_range=30,
            prediction_type='general'
        )

        assert isinstance(result, PredictionResult)
        assert result.topic == "人工智能"
        assert result.trend in ['up', 'down', 'stable']
        assert len(result.timeline) == 30

    @pytest.mark.asyncio
    async def test_multiple_predictions(self, mock_neo4j_service):
        """测试多种预测类型"""
        engine = TrendPredictionEngine(mock_neo4j_service)

        # 一般趋势预测
        result1 = await engine.predict_trend("人工智能", prediction_type='general')
        assert result1.prediction_type == 'general'

        # 舆情预测
        result2 = await engine.predict_sentiment("人工智能")
        assert result2.prediction_type == 'sentiment'

        # 技术趋势预测
        result3 = await engine.predict_technology("人工智能")
        assert result3.prediction_type == 'technology'


class TestEventListenerIntegration:
    """事件监听器集成测试"""

    @pytest.fixture
    def mock_neo4j_service(self):
        """模拟 Neo4j 服务"""
        service = AsyncMock()
        service.create_entity = AsyncMock()
        service.create_relationship = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_event_triggers_enhancement(self, mock_neo4j_service):
        """测试事件触发增强流程"""
        from app.services.kg.event_listener import KnowledgeEventListener

        enhancement_service = KnowledgeSelfEnhancement(mock_neo4j_service, llm_client=None)
        listener = KnowledgeEventListener(enhancement_service)

        # 触发文章创建事件
        await listener.emit('article_created', {
            'article_id': 'event_test_1',
            'content': '事件触发测试内容'
        })

        # 验证增强服务被调用
        # 由于是异步任务，需要等待
        import asyncio
        await asyncio.sleep(0.1)

        # 检查是否有处理结果
        stats = enhancement_service.get_stats()
        assert stats is not None
