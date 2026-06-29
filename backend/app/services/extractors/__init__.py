"""
内容提取器模块
包含多种提取器实现，支持智能选择和降级
"""

from app.services.extractors.base import BaseExtractor, ExtractedContent
from app.services.extractors.readability_extractor import ReadabilityExtractor
from app.services.extractors.density_extractor import DensityExtractor
from app.services.extractors.trafilatura_extractor import TrafilaturaExtractor

__all__ = [
    "BaseExtractor",
    "ExtractedContent",
    "ReadabilityExtractor",
    "DensityExtractor",
    "TrafilaturaExtractor",
]