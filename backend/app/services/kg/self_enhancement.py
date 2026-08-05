"""
知识自增强循环核心服务

实现知识库的自动学习、关联、预测和优化循环。
借鉴卡帕西思想，建立"输入→理解→总结→关联→预测→输出→反馈"的闭环。
"""

import time
import logging
import re
import hashlib
import json
from difflib import SequenceMatcher
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field

from .prompt_templates import PromptTemplateManager, template_manager

logger = logging.getLogger(__name__)


@dataclass
class KnowledgePoint:
    """知识点数据类"""
    id: str
    article_id: str
    title: str
    content: str
    category: str  # concept/argument/fact/method
    confidence: float
    keywords: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    source_span: Optional[str] = None
    source_url: Optional[str] = None
    source_published_at: Optional[str] = None
    status: str = "candidate"
    model_name: Optional[str] = None
    prompt_version: str = "kp_extraction:v1"
    content_hash: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class Association:
    """知识点关联数据类"""
    id: str
    source_id: str
    target_id: str
    relation_type: str
    strength: float
    evidence: str = ""
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class SelfEnhancementResult:
    """自增强循环结果"""
    enhancement_id: str
    article_id: str
    status: str  # pending/processing/completed/failed
    progress: int = 0
    knowledge_points_count: int = 0
    associations_count: int = 0
    summary: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    input_hash: str = ""


class KnowledgeSelfEnhancement:
    """
    知识自增强循环管理器

    核心功能：
    1. 处理新文章，启动自增强循环
    2. LLM 驱动的知识点提取
    3. 知识关联发现
    4. 知识总结生成
    5. 统计信息维护
    """

    def __init__(self, kg_service, llm_client=None, prompt_manager: Optional[PromptTemplateManager] = None):
        """
        初始化知识自增强循环服务

        Args:
            kg_service: Neo4jService 实例
            llm_client: LLM 客户端（可选，用于 LLM 驱动的提取）
            prompt_manager: 提示词模板管理器（可选，默认使用全局实例）
        """
        self.kg_service = kg_service
        self.llm_client = llm_client
        self.prompt_manager = prompt_manager or template_manager
        self._processing_tasks: Dict[str, SelfEnhancementResult] = {}

    async def process_new_article(
        self,
        article_id: str,
        article_content: str,
        source_url: Optional[str] = None,
        source_published_at: Optional[str] = None,
    ) -> SelfEnhancementResult:
        """
        处理新文章，启动自增强循环

        流程：
        1. 文章预处理（清洗、分段）
        2. 实体抽取（LLM 驱动）
        3. 关系发现（LLM + 规则）
        4. 知识点提取（LLM 总结）
        5. 关联发现（图算法）
        6. 知识输出（新知识点入库）

        Args:
            article_id: 文章 ID
            article_content: 文章内容

        Returns:
            SelfEnhancementResult: 处理结果
        """
        # 检查是否已处理过该文章，如果是则更新而不是创建新记录
        content_hash = hashlib.sha256((article_content or "").encode("utf-8")).hexdigest()
        existing_task = None
        for task in self._processing_tasks.values():
            if task.article_id == article_id and getattr(task, "input_hash", None) == content_hash:
                existing_task = task
                break

        if existing_task:
            # 更新现有记录
            enhancement_id = existing_task.enhancement_id
            existing_task.status = 'processing'
            existing_task.progress = 0
            existing_task.knowledge_points_count = 0
            existing_task.associations_count = 0
            existing_task.error_message = None
            existing_task.input_hash = content_hash
            result = existing_task
        else:
            # 创建新记录
            enhancement_id = f"enh_{article_id}_{content_hash[:16]}"
            result = SelfEnhancementResult(
                enhancement_id=enhancement_id,
                article_id=article_id,
                status='processing',
                progress=0,
                input_hash=content_hash,
            )
            self._processing_tasks[enhancement_id] = result

        try:
            logger.info(f"Starting self-enhancement for article: {article_id}")

            # 步骤 1: 文章预处理 (10%)
            processed_content = self._preprocess_article(article_content)
            result.progress = 10

            # 步骤 2: 提取知识点 (40%)
            knowledge_points = await self._extract_knowledge_points(
                article_id,
                processed_content,
                source_url=source_url,
                source_published_at=source_published_at,
                content_hash=content_hash,
            )
            result.progress = 50
            result.knowledge_points_count = len(knowledge_points)

            # 步骤 3: 发现关联 (30%)
            associations = await self._discover_associations(knowledge_points)
            cross_document_associations = await self._discover_cross_document_associations(
                knowledge_points
            )
            associations.extend(cross_document_associations)
            result.progress = 80
            result.associations_count = len(associations)

            # 步骤 4: 生成总结 (10%)
            summary = await self._generate_summary(
                article_content, knowledge_points, associations
            )
            result.summary = summary
            result.progress = 100

            # 完成
            result.status = 'completed'
            result.completed_at = datetime.now()

            logger.info(
                f"Self-enhancement completed: {result.knowledge_points_count} points, "
                f"{result.associations_count} associations"
            )

        except Exception as e:
            logger.error(f"Self-enhancement failed for article {article_id}: {e}")
            result.status = 'failed'
            result.error_message = str(e)

        return result

    def _preprocess_article(self, content: str) -> str:
        """
        文章预处理

        - 移除 HTML 标签
        - 合并多余空白
        - 清洗特殊字符
        """
        if not content:
            return ""

        # 移除 HTML 标签
        content = re.sub(r'<[^>]+>', '', content)
        # 合并空白
        content = re.sub(r'\s+', ' ', content)
        # 移除多余标点
        content = re.sub(r'[。，、；：！？]{2,}', lambda m: m.group()[0], content)

        return content.strip()

    async def _extract_knowledge_points(
        self,
        article_id: str,
        content: str,
        source_url: Optional[str] = None,
        source_published_at: Optional[str] = None,
        content_hash: str = "",
    ) -> List[KnowledgePoint]:
        """
        从内容中提取知识点

        如果有 LLM 客户端，使用 LLM 进行智能提取；
        否则使用规则提取。
        """
        knowledge_points = []

        if self.llm_client:
            # 使用 LLM 提取
            raw_points = await self._llm_extract_points(content)
        else:
            # 使用规则提取
            raw_points = self._rule_based_extract_points(content)

        for i, point_data in enumerate(raw_points):
            point_text = str(point_data.get("content", "")).strip()
            point_key = "\x1f".join((article_id, point_data.get("title", ""), point_text))
            point_id = f"kp-{hashlib.sha256(point_key.encode('utf-8')).hexdigest()[:32]}"
            evidence = [item for item in self._normalize_evidence(point_data.get("evidence")) if item in content]
            source_span = str(point_data.get("source_span") or "").strip()
            if source_span and source_span not in content:
                source_span = None
            if not source_span and point_text in content:
                source_span = point_text
            point = KnowledgePoint(
                id=point_id,
                article_id=article_id,
                title=point_data.get('title', f'知识点 {i+1}'),
                content=point_data.get('content', ''),
                category=point_data.get('category', 'concept'),
                confidence=point_data.get('confidence', 0.7),
                keywords=point_data.get('keywords', []),
                evidence=evidence,
                source_span=source_span or point_text,
                source_url=source_url,
                source_published_at=source_published_at,
                model_name=point_data.get("model_name"),
                content_hash=content_hash,
            )
            knowledge_points.append(point)

            # 存储到图数据库
            await self._store_knowledge_point(point)

        return knowledge_points

    async def _llm_extract_points(self, content: str) -> List[Dict]:
        """使用 LLM 提取知识点"""
        try:
            # 使用模板管理器渲染提示词
            prompt = self.prompt_manager.render_template(
                "kp_extraction",
                {"content": content[:2000], "max_points": "10", "language": "zh"}
            )

            # 使用LLMService的non_stream_chat方法
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.non_stream_chat(
                model_id=None,  # 使用默认模型
                messages=messages,
                temperature=0.7,
                max_tokens=2000
            )

            parsed = self._parse_structured_points(response)
            if parsed is not None:
                return parsed
            return []

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return self._rule_based_extract_points(content)

    @staticmethod
    def _parse_structured_points(response: str) -> Optional[List[Dict[str, Any]]]:
        """解析并校验 LLM 知识声明，拒绝非对象数组和明显无效字段。"""
        if not response:
            return None
        candidates = [response.strip()]
        json_match = re.search(r"\[[\s\S]*\]", response)
        if json_match and json_match.group() not in candidates:
            candidates.append(json_match.group())
        for candidate in candidates:
            try:
                payload = json.loads(candidate)
            except (TypeError, json.JSONDecodeError):
                continue
            if not isinstance(payload, list):
                continue
            valid = []
            for item in payload[:10]:
                if not isinstance(item, dict):
                    continue
                title = str(item.get("title") or "").strip()
                content = str(item.get("content") or "").strip()
                if not title or not content:
                    continue
                try:
                    confidence = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
                except (TypeError, ValueError):
                    confidence = 0.5
                keywords = item.get("keywords") or []
                if not isinstance(keywords, list):
                    keywords = [str(keywords)]
                valid.append({
                    "title": title,
                    "content": content,
                    "category": str(item.get("category") or "concept"),
                    "confidence": confidence,
                    "keywords": [str(value).strip() for value in keywords if str(value).strip()][:10],
                    "evidence": item.get("evidence") or [content],
                    "source_span": str(item.get("source_span") or content),
                })
            return valid
        return None

    @staticmethod
    def _normalize_evidence(value: Any) -> List[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value.strip()] if value.strip() else []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()][:5]
        return [str(value).strip()]

    def _rule_based_extract_points(self, content: str) -> List[Dict]:
        """基于规则提取知识点"""
        points = []
        sentences = re.split(r'[。！？]', content)

        # 提取包含关键词的句子
        keywords_map = {
            'concept': ['是', '定义', '概念', '指', '表示'],
            'argument': ['认为', '观点', '主张', '建议', '应该'],
            'fact': ['数据', '统计', '案例', '例如', '比如'],
            'method': ['方法', '技术', '算法', '流程', '步骤']
        }

        for sentence in sentences[:20]:  # 只处理前 20 句
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            for category, keywords in keywords_map.items():
                if any(kw in sentence for kw in keywords):
                    points.append({
                        'title': sentence[:30] + '...' if len(sentence) > 30 else sentence,
                        'content': sentence,
                        'category': category,
                        'confidence': 0.6,
                        'keywords': self._extract_keywords(sentence)
                    })
                    break

            if len(points) >= 10:
                break

        # 如果没有提取到，创建默认知识点
        if not points and content:
            points.append({
                'title': '文章摘要',
                'content': content[:200],
                'category': 'concept',
                'confidence': 0.5,
                'keywords': []
            })

        return points

    def _extract_keywords(self, text: str) -> List[str]:
        """提取关键词（简单实现）"""
        # 简单的关键词提取：取名词和动词
        import jieba
        words = jieba.lcut(text)
        # 过滤停用词和短词
        keywords = [w for w in words if len(w) >= 2][:5]
        return keywords

    async def _store_knowledge_point(self, point: KnowledgePoint):
        """存储知识点到图数据库"""
        try:
            await self.kg_service.create_entity(
                # 使用稳定 ID 作为图节点 name，避免相同标题覆盖不同文章的知识声明。
                name=point.id,
                entity_type='KnowledgePoint',
                properties={
                    'id': point.id,
                    'title': point.title,
                    'article_id': point.article_id,
                    'content': point.content,
                    'category': point.category,
                    'confidence': point.confidence,
                    'keywords': point.keywords,
                    'created_at': point.created_at.isoformat(),
                    'evidence': point.evidence,
                    'source_span': point.source_span or "",
                    'source_url': point.source_url or "",
                    'source_published_at': point.source_published_at or "",
                    'status': point.status,
                    'model_name': point.model_name or "rule_based",
                    'prompt_version': point.prompt_version,
                    'content_hash': point.content_hash,
                }
            )
        except Exception as e:
            logger.error(f"Failed to store knowledge point: {e}")

    async def _discover_cross_document_associations(
        self, knowledge_points: List[KnowledgePoint]
    ) -> List[Association]:
        """召回其他文章中的相似知识声明，写入待审核候选关系。"""
        if not knowledge_points or not hasattr(self.kg_service, "execute"):
            return []

        try:
            rows = await self.kg_service.execute(
                """
                MATCH (n:Entity)
                WHERE n.entity_type = 'KnowledgePoint'
                RETURN n
                LIMIT 500
                """
            )
        except Exception as exc:
            logger.warning("跨文档知识召回失败: %s", exc)
            return []
        if not isinstance(rows, list):
            return []

        candidates = []
        current_ids = {point.id for point in knowledge_points}
        for point in knowledge_points:
            for row in rows:
                node = row.get("n") if isinstance(row, dict) else None
                if not node:
                    continue
                node_id = str(node.get("id") or "")
                if not node_id or node_id in current_ids:
                    continue
                if str(node.get("article_id") or "") == point.article_id:
                    continue
                candidate_title = str(node.get("title") or node.get("name") or "")
                candidate_content = str(node.get("content") or "")
                candidate_keywords = set(node.get("keywords") or [])
                if not candidate_title or not candidate_content:
                    continue

                keyword_union = set(point.keywords) | candidate_keywords
                keyword_score = (
                    len(set(point.keywords) & candidate_keywords) / len(keyword_union)
                    if keyword_union else 0.0
                )
                title_score = SequenceMatcher(
                    None, point.title.casefold(), candidate_title.casefold()
                ).ratio()
                content_score = SequenceMatcher(
                    None, point.content[:300].casefold(), candidate_content[:300].casefold()
                ).ratio()
                score = round(0.45 * content_score + 0.35 * title_score + 0.20 * keyword_score, 4)
                if score < 0.55:
                    continue

                positive_markers = ("支持", "表明", "促进", "增加", "提升", "有效", "成功")
                negative_markers = ("不支持", "未发现", "没有", "无法", "否认", "下降", "减少", "失败")
                point_positive = any(marker in point.content for marker in positive_markers)
                point_negative = any(marker in point.content for marker in negative_markers)
                candidate_positive = any(marker in candidate_content for marker in positive_markers)
                candidate_negative = any(marker in candidate_content for marker in negative_markers)
                polarity_conflict = (
                    title_score >= 0.7
                    and keyword_score >= 0.3
                    and ((point_positive and candidate_negative) or (point_negative and candidate_positive))
                )
                relation_type = (
                    "conflict_candidate"
                    if polarity_conflict
                    else "duplicate_candidate" if score >= 0.85 else "related_candidate"
                )
                association_id = f"assoc-{hashlib.sha256((point.id + node_id).encode('utf-8')).hexdigest()[:32]}"
                association = Association(
                    id=association_id,
                    source_id=point.id,
                    target_id=node_id,
                    relation_type=relation_type,
                    strength=score,
                    evidence=(
                        f"跨文档候选：标题相似度={title_score:.2f}，"
                        f"内容相似度={content_score:.2f}，关键词相似度={keyword_score:.2f}"
                    ),
                )
                candidates.append(association)

        unique = {}
        for association in candidates:
            unique[association.id] = association
            await self._store_candidate_association(association)
        return list(unique.values())

    async def _store_candidate_association(self, association: Association):
        """保存待审核的跨文档候选，不将其视为正式关系。"""
        try:
            await self.kg_service.create_knowledge_candidate(
                candidate_id=association.id,
                source_id=association.source_id,
                target_id=association.target_id,
                candidate_type=association.relation_type,
                strength=association.strength,
                evidence=association.evidence,
            )
        except Exception as exc:
            logger.warning("保存跨文档候选关系失败: %s", exc)

    async def _discover_associations(
        self, knowledge_points: List[KnowledgePoint]
    ) -> List[Association]:
        """
        发现知识点之间的关联

        算法：
        1. 基于关键词共现
        2. 基于内容相似度
        3. 基于图结构
        """
        associations = []

        for i, point_a in enumerate(knowledge_points):
            for point_b in knowledge_points[i+1:]:
                association = self._calculate_association(point_a, point_b)
                if association and association.strength > 0.3:
                    associations.append(association)
                    await self._store_association(association)

        return associations

    def _calculate_association(
        self, point_a: KnowledgePoint, point_b: KnowledgePoint
    ) -> Optional[Association]:
        """计算两个知识点之间的关联"""
        # 基于关键词计算相似度
        keywords_a = set(point_a.keywords)
        keywords_b = set(point_b.keywords)

        if not keywords_a or not keywords_b:
            return None

        # Jaccard 相似度
        intersection = len(keywords_a & keywords_b)
        union = len(keywords_a | keywords_b)

        if union == 0:
            return None

        strength = intersection / union

        # 确定关系类型
        if point_a.category == point_b.category:
            relation_type = 'related_to'
        elif point_a.category == 'concept' and point_b.category == 'argument':
            relation_type = 'supports'
        elif point_a.category == 'fact' and point_b.category == 'method':
            relation_type = 'demonstrates'
        else:
            relation_type = 'related_to'

        assoc_id = f"assoc_{point_a.id}_{point_b.id}"

        return Association(
            id=assoc_id,
            source_id=point_a.id,
            target_id=point_b.id,
            relation_type=relation_type,
            strength=strength,
            evidence=f"关键词重叠: {keywords_a & keywords_b}"
        )

    async def _store_association(self, association: Association):
        """存储关联到图数据库"""
        try:
            await self.kg_service.create_relationship(
                source_name=association.source_id,
                target_name=association.target_id,
                relationship_type=association.relation_type,
                properties={
                    'id': association.id,
                    'strength': association.strength,
                    'evidence': association.evidence,
                    'created_at': association.created_at.isoformat()
                }
            )
        except Exception as e:
            logger.error(f"Failed to store association: {e}")

    async def _generate_summary(
        self,
        article_content: str,
        knowledge_points: List[KnowledgePoint],
        associations: List[Association]
    ) -> str:
        """
        生成知识总结

        包含：
        - 核心观点
        - 关键知识点
        - 知识点关联
        - 应用价值
        """
        if self.llm_client:
            return await self._llm_generate_summary(
                article_content, knowledge_points, associations
            )
        else:
            return self._rule_based_summary(knowledge_points, associations)

    async def _llm_generate_summary(
        self,
        article_content: str,
        knowledge_points: List[KnowledgePoint],
        associations: List[Association]
    ) -> str:
        """使用 LLM 生成总结"""
        try:
            # 准备变量
            points_text = "\n".join([
                f"- [{p.category}] {p.title}: {p.content[:100]}"
                for p in knowledge_points[:10]
            ])

            associations_text = "\n".join([
                f"- {a.source_id} -> {a.target_id} ({a.relation_type})"
                for a in associations[:10]
            ])

            # 使用模板管理器渲染提示词
            prompt = self.prompt_manager.render_template(
                "kp_summary",
                {
                    "article_content": article_content[:500],
                    "knowledge_points": points_text,
                    "associations": associations_text or "[]"
                }
            )

            # 使用LLMService的non_stream_chat方法
            messages = [{"role": "user", "content": prompt}]
            response = await self.llm_client.non_stream_chat(
                model_id=None,  # 使用默认模型
                messages=messages,
                temperature=0.7,
                max_tokens=1000
            )
            return response

        except Exception as e:
            logger.error(f"LLM summary generation failed: {e}")
            return self._rule_based_summary(knowledge_points, associations)

    def _rule_based_summary(
        self,
        knowledge_points: List[KnowledgePoint],
        associations: List[Association]
    ) -> str:
        """基于规则生成总结"""
        summary_parts = []

        # 统计各类知识点
        categories = {}
        for point in knowledge_points:
            categories[point.category] = categories.get(point.category, 0) + 1

        summary_parts.append(f"本文共提取了 {len(knowledge_points)} 个知识点：")

        for cat, count in categories.items():
            cat_names = {
                'concept': '概念',
                'argument': '观点',
                'fact': '事实',
                'method': '方法'
            }
            summary_parts.append(f"- {cat_names.get(cat, cat)}: {count} 个")

        if associations:
            summary_parts.append(f"\n发现 {len(associations)} 个知识关联。")

        # 列出主要知识点
        summary_parts.append("\n主要知识点：")
        for point in knowledge_points[:5]:
            summary_parts.append(f"- {point.title}")

        return "\n".join(summary_parts)

    def get_processing_status(self, enhancement_id: str) -> Optional[SelfEnhancementResult]:
        """获取处理任务状态"""
        return self._processing_tasks.get(enhancement_id)

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        从数据库和Neo4j查询统计数据
        """
        try:
            from app.core.database import get_session_local
            from app.models.article import Article

            SessionLocal = get_session_local()
            session = SessionLocal()

            try:
                # 从数据库查询已处理文章数
                processed_count = session.query(Article).filter(
                    Article.kg_status.in_(['success', 'partial'])
                ).count()

                # 获取最后处理时间
                last_article = session.query(Article).filter(
                    Article.kg_status.in_(['success', 'partial']),
                    Article.kg_processed_at.isnot(None)
                ).order_by(Article.kg_processed_at.desc()).first()

                last_processed_at = (
                    last_article.kg_processed_at if last_article else None
                )

                # 从Neo4j查询知识点和关联数量
                total_points = 0
                total_associations = 0

                try:
                    import asyncio
                    from app.services.kg.graph import Neo4jService

                    async def get_neo4j_stats():
                        neo4j = Neo4jService()
                        await neo4j.connect()
                        try:
                            # 查询知识点数量
                            result = await neo4j.execute(
                                'MATCH (n:Entity) WHERE n.entity_type = "KnowledgePoint" RETURN count(n) as count'
                            )
                            kp_count = result[0]['count'] if result else 0

                            # 查询关联数量
                            result = await neo4j.execute(
                                'MATCH (a:Entity)-[r]->(b:Entity) WHERE a.entity_type = "KnowledgePoint" AND b.entity_type = "KnowledgePoint" RETURN count(r) as count'
                            )
                            rel_count = result[0]['count'] if result else 0

                            return kp_count, rel_count
                        finally:
                            await neo4j.close()

                    # 运行异步查询
                    total_points, total_associations = asyncio.run(get_neo4j_stats())
                except Exception as neo4j_error:
                    logger.warning(f"从Neo4j获取统计数据失败: {neo4j_error}")

                # 计算平均值
                average_points_per_article = (
                    total_points / processed_count if processed_count > 0 else 0
                )
                average_associations_per_point = (
                    total_associations / total_points if total_points > 0 else 0
                )

                return {
                    'total_articles_processed': processed_count,
                    'total_knowledge_points': total_points,
                    'total_associations': total_associations,
                    'average_points_per_article': average_points_per_article,
                    'average_associations_per_point': average_associations_per_point,
                    'last_processed_at': last_processed_at
                }
            finally:
                session.close()
        except Exception as e:
            logger.error(f"获取统计数据失败: {e}")
            # 降级到内存统计
            completed = [
                r for r in self._processing_tasks.values()
                if r.status == 'completed'
            ]

            total_points = sum(r.knowledge_points_count for r in completed)
            total_associations = sum(r.associations_count for r in completed)

            return {
                'total_articles_processed': len(completed),
                'total_knowledge_points': total_points,
                'total_associations': total_associations,
                'average_points_per_article': (
                    total_points / len(completed) if completed else 0
                ),
                'average_associations_per_point': (
                    total_associations / total_points if total_points > 0 else 0
                ),
                'last_processed_at': (
                    max(r.completed_at for r in completed) if completed else None
                )
            }

    def list_prompt_templates(self, category: Optional[str] = None) -> List[Dict]:
        """
        列出可用的提示词模板

        Args:
            category: 可选，按分类筛选

        Returns:
            模板列表
        """
        templates = self.prompt_manager.list_templates(category)
        return [self.prompt_manager.get_template_for_frontend(t.id) for t in templates]

    def get_prompt_template(self, template_id: str) -> Optional[Dict]:
        """
        获取指定的提示词模板

        Args:
            template_id: 模板 ID

        Returns:
            模板信息
        """
        return self.prompt_manager.get_template_for_frontend(template_id)
