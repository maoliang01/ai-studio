"""
知识库事件监听器

监听知识库事件，自动触发自增强循环。
"""

import logging
from typing import Callable, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class KnowledgeEventListener:
    """知识库事件监听器"""

    def __init__(self, self_enhancement_service):
        """
        初始化事件监听器

        Args:
            self_enhancement_service: KnowledgeSelfEnhancement 实例
        """
        self.self_enhancement = self_enhancement_service
        self.handlers: Dict[str, List[Callable]] = {}
        self._register_default_handlers()

    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self.register_handler('article_created', self._on_article_created)
        self.register_handler('article_updated', self._on_article_updated)

    def register_handler(self, event_type: str, handler: Callable):
        """注册事件处理器"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)

    async def emit(self, event_type: str, data: Dict[str, Any]):
        """触发事件"""
        logger.info(f"触发事件: {event_type}")

        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    await handler(data)
                except Exception as e:
                    logger.error(f"事件处理器错误 {event_type}: {e}")

    async def _on_article_created(self, data: Dict[str, Any]):
        """文章创建事件"""
        article_id = data.get('article_id')
        article_content = data.get('content', '')

        if article_id and article_content:
            logger.info(f"文章创建: {article_id}，启动自增强循环")
            await self.self_enhancement.process_new_article(article_id, article_content)

    async def _on_article_updated(self, data: Dict[str, Any]):
        """文章更新事件"""
        article_id = data.get('article_id')
        article_content = data.get('content', '')

        if article_id and article_content:
            logger.info(f"文章更新: {article_id}，重新处理")
            await self.self_enhancement.process_new_article(article_id, article_content)


# 全局事件监听器实例
_event_listener = None


def get_event_listener(self_enhancement_service=None):
    """获取全局事件监听器实例"""
    global _event_listener
    if _event_listener is None and self_enhancement_service:
        _event_listener = KnowledgeEventListener(self_enhancement_service)
    return _event_listener
