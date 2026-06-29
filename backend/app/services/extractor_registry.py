"""
提取器注册表
管理所有提取器，支持智能选择和降级
"""

import logging
from typing import List, Optional

from app.services.extractors.base import BaseExtractor, ExtractedContent
from app.services.extractors import (
    ReadabilityExtractor,
    DensityExtractor,
    TrafilaturaExtractor,
)
from app.services.website_classifier import WebsiteProfile

logger = logging.getLogger(__name__)


class ExtractorRegistry:
    """提取器注册表 - 智能选择最佳提取器"""

    def __init__(self):
        self._extractors: List[BaseExtractor] = []
        self._register_default_extractors()

    def _register_default_extractors(self) -> None:
        """注册默认提取器（按优先级排序）"""
        extractors = [
            ReadabilityExtractor(),   # 优先级 10
            TrafilaturaExtractor(),    # 优先级 20
            DensityExtractor(),        # 优先级 30
        ]

        for extractor in extractors:
            self._extractors.append(extractor)
            logger.info(f"注册提取器: {extractor.name} (优先级: {extractor.priority})")

    def register(self, extractor: BaseExtractor) -> None:
        """注册新的提取器"""
        self._extractors.append(extractor)
        # 按优先级排序
        self._extractors.sort(key=lambda x: x.priority)
        logger.info(f"注册提取器: {extractor.name}")

    def get_all_extractors(self) -> List[BaseExtractor]:
        """获取所有提取器（按优先级排序）"""
        return sorted(self._extractors, key=lambda x: x.priority)

    def get_best_extractor(self, profile: WebsiteProfile) -> BaseExtractor:
        """根据网站类型获取最佳提取器"""
        extractors = self.get_all_extractors()

        # 尝试找到支持该网站类型的提取器
        for extractor in extractors:
            if extractor.supports(profile.website_type):
                logger.info(f"选择提取器: {extractor.name} (网站类型: {profile.website_type.value})")
                return extractor

        # 默认返回第一个（最高优先级）
        return extractors[0]

    def extract_with_fallback(
        self,
        html: str,
        url: str = "",
        profile: Optional[WebsiteProfile] = None,
    ) -> ExtractedContent:
        """降级提取：尝试多个提取器直到成功"""
        # 获取所有提取器按优先级排序
        extractors = self.get_all_extractors()

        # 如果有网站类型偏好，优先尝试推荐的提取器
        if profile:
            recommended_name = profile.recommended_extractor
            recommended_extractor = None

            # 找到推荐的提取器
            for e in extractors:
                if e.name == recommended_name:
                    recommended_extractor = e
                    break

            # 如果找到推荐的，优先尝试
            if recommended_extractor:
                try:
                    result = recommended_extractor.extract(html, url)
                    if result.is_valid():
                        logger.info(f"推荐提取器 {recommended_extractor.name} 成功")
                        return result
                except Exception as e:
                    logger.warning(f"推荐提取器 {recommended_extractor.name} 失败: {e}")

        # 尝试所有提取器
        for extractor in extractors:
            try:
                result = extractor.extract(html, url)
                if result.is_valid():
                    logger.info(f"提取器 {extractor.name} 成功，提取 {result.length} 字符")
                    return result
                else:
                    logger.debug(f"提取器 {extractor.name} 结果无效，长度: {result.length}")
            except Exception as e:
                logger.warning(f"提取器 {extractor.name} 失败: {e}")
                continue

        # 所有提取器都失败
        logger.error("所有提取器都失败")
        return ExtractedContent()


# 单例实例
registry = ExtractorRegistry()


def get_extractor_registry() -> ExtractorRegistry:
    """获取提取器注册表"""
    return registry


def smart_extract(html: str, url: str = "", profile: Optional[WebsiteProfile] = None) -> ExtractedContent:
    """快捷函数：智能提取内容"""
    return registry.extract_with_fallback(html, url, profile)