"""
趋势预测引擎

基于知识图谱进行趋势预测，包括技术趋势、舆情趋势等。
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """预测结果"""
    topic: str
    trend: str  # up/down/stable
    confidence: float
    factors: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    prediction_type: str
    generated_at: str


class TrendPredictionEngine:
    """趋势预测引擎"""

    def __init__(self, kg_service):
        """
        初始化预测引擎

        Args:
            kg_service: Neo4jService 实例
        """
        self.kg_service = kg_service

    async def predict_trend(
        self,
        topic: str,
        time_range: int = 30,
        prediction_type: str = 'general'
    ) -> PredictionResult:
        """
        预测趋势

        Args:
            topic: 预测主题
            time_range: 预测天数
            prediction_type: 预测类型 (general/technology/sentiment)

        Returns:
            PredictionResult: 预测结果
        """
        try:
            # 1. 收集历史数据
            historical_data = await self._collect_historical_data(topic)

            # 2. 分析影响因素
            factors = await self._analyze_factors(topic)

            # 3. 生成预测
            prediction = self._generate_prediction(
                historical_data, factors, time_range, prediction_type, topic
            )

            return prediction

        except Exception as e:
            logger.error(f"趋势预测失败: {e}")
            # 返回默认预测
            return PredictionResult(
                topic=topic,
                trend='stable',
                confidence=0.3,
                factors=[],
                timeline=self._generate_default_timeline(time_range),
                prediction_type=prediction_type,
                generated_at=datetime.now().isoformat()
            )

    async def _collect_historical_data(self, topic: str) -> Dict[str, Any]:
        """收集历史数据"""
        try:
            # 搜索相关实体
            entities = await self.kg_service.search_entities(topic, limit=10)

            # 获取关联实体
            related_entities = []
            for entity in entities[:5]:
                try:
                    relationships = await self.kg_service.get_relationships(entity.name)
                    related_entities.extend(relationships)
                except Exception:
                    pass

            return {
                'entities': entities,
                'related_entities': related_entities,
                'entity_count': len(entities)
            }
        except Exception as e:
            logger.warning(f"收集历史数据失败: {e}")
            return {'entities': [], 'related_entities': [], 'entity_count': 0}

    async def _analyze_factors(self, topic: str) -> List[Dict[str, Any]]:
        """分析影响因素"""
        factors = []

        try:
            # 获取相关实体作为因素
            entities = await self.kg_service.search_entities(topic, limit=5)
            for entity in entities:
                factors.append({
                    'type': 'entity',
                    'name': entity.name,
                    'entity_type': entity.entity_type,
                    'strength': 0.5
                })
        except Exception as e:
            logger.warning(f"分析影响因素失败: {e}")

        return factors[:5]  # 最多返回5个因素

    def _generate_prediction(
        self,
        historical_data: Dict[str, Any],
        factors: List[Dict[str, Any]],
        time_range: int,
        prediction_type: str,
        topic: str
    ) -> PredictionResult:
        """生成预测"""

        # 计算基础趋势
        entity_count = historical_data.get('entity_count', 0)
        factor_count = len(factors)

        # 简单的趋势判断
        if entity_count > 10 and factor_count > 3:
            trend = 'up'
            confidence = 0.7
        elif entity_count < 3:
            trend = 'stable'
            confidence = 0.5
        else:
            trend = 'up'
            confidence = 0.6

        # 生成时间线
        timeline = self._generate_timeline(trend, time_range)

        return PredictionResult(
            topic=topic,
            trend=trend,
            confidence=confidence,
            factors=factors,
            timeline=timeline,
            prediction_type=prediction_type,
            generated_at=datetime.now().isoformat()
        )

    def _generate_timeline(self, trend: str, days: int) -> List[Dict[str, Any]]:
        """生成时间线预测"""
        timeline = []
        base_value = 100

        trend_factor = {'up': 0.02, 'down': -0.02, 'stable': 0}.get(trend, 0)

        for day in range(days):
            date = datetime.now() + timedelta(days=day)
            predicted_value = base_value * (1 + trend_factor * day)

            timeline.append({
                'date': date.strftime('%Y-%m-%d'),
                'predicted_value': round(predicted_value, 2),
                'confidence_interval': {
                    'lower': round(predicted_value * 0.9, 2),
                    'upper': round(predicted_value * 1.1, 2)
                }
            })

        return timeline

    def _generate_default_timeline(self, days: int) -> List[Dict[str, Any]]:
        """生成默认时间线"""
        return self._generate_timeline('stable', days)

    async def predict_sentiment(self, topic: str) -> PredictionResult:
        """预测舆情趋势"""
        return await self.predict_trend(topic, prediction_type='sentiment')

    async def predict_technology(self, topic: str) -> PredictionResult:
        """预测技术趋势"""
        return await self.predict_trend(topic, prediction_type='technology')
