"""知识综合文档生成与发布服务。"""

import hashlib
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.models.article import Article
from app.models.synthesis import KnowledgeSynthesis
from app.services.kg.prompt_templates import template_manager

logger = logging.getLogger("ai-studio.knowledge_synthesis")


class KnowledgeSynthesisService:
    """将多个来源知识声明汇总为可审核、可回灌的知识文档。"""

    PROMPT_VERSION = "knowledge_synthesis:v1"

    def __init__(self, kg_service, llm_client=None):
        self.kg_service = kg_service
        self.llm_client = llm_client

    async def create_auto_draft(self, db, topic: Optional[str] = None, limit: int = 5) -> KnowledgeSynthesis:
        """自动发现一个候选事件并用其证据文档生成综合草稿。"""
        from app.services.kg.event_discovery import EventDiscoveryService

        candidates = EventDiscoveryService().discover(db, limit=max(5, limit))
        if not candidates:
            raise ValueError("暂时没有可用于综合的候选事件")
        candidate = next((item for item in candidates if topic and topic in item["title"]), candidates[0])
        article_ids = [item["id"] for item in candidate["evidence_articles"]]
        return await self.create_draft(
            db=db,
            topic=topic.strip() if topic else candidate["topic"],
            article_ids=article_ids,
        )

    async def create_draft(
        self,
        db,
        topic: str,
        article_ids: List[str],
        parent_synthesis_id: Optional[str] = None,
    ) -> KnowledgeSynthesis:
        articles = db.query(Article).filter(Article.id.in_(article_ids)).all()
        valid_article_ids = [str(article.id) for article in articles]
        if not valid_article_ids:
            raise ValueError("没有找到可用的来源文章")

        points = await self._load_knowledge_points(valid_article_ids)
        context = self._format_context(points, articles)
        previous = await self._load_prior_syntheses(topic)
        if previous:
            context += "\n\n## 历史已发布综合文档（仅用于比较变化）\n" + self._format_prior_context(previous)
        generated = await self._generate(topic, context, points, articles)
        parent = None
        iteration = 1
        if parent_synthesis_id:
            parent = db.query(KnowledgeSynthesis).filter(
                KnowledgeSynthesis.id == parent_synthesis_id
            ).first()
            if parent is None:
                raise ValueError("父版本知识综合文档不存在")
            if parent.topic.strip() != topic.strip():
                raise ValueError("父版本主题与当前主题不一致")
            iteration = parent.iteration + 1
        fingerprint = hashlib.sha256(
            "\x1f".join([
                topic.strip(),
                self.PROMPT_VERSION,
                str(parent_synthesis_id or ""),
                *sorted(valid_article_ids),
            ]).encode("utf-8")
        ).hexdigest()[:32]

        synthesis = KnowledgeSynthesis(
            id=f"synth-{fingerprint}",
            topic=topic.strip(),
            title=generated["title"],
            content=generated["content"],
            summary=generated["summary"],
            source_document_ids=valid_article_ids,
            source_claim_ids=[str(point.get("id")) for point in points if point.get("id")],
            iteration=iteration,
            parent_synthesis_id=parent_synthesis_id,
            model_name=generated.get("model_name"),
            prompt_version=self.PROMPT_VERSION,
            quality_score=generated.get("quality_score"),
            status="draft",
        )
        existing = db.query(KnowledgeSynthesis).filter(KnowledgeSynthesis.id == synthesis.id).first()
        if existing:
            return existing
        db.add(synthesis)
        db.commit()
        db.refresh(synthesis)
        return synthesis

    async def publish(self, db, synthesis_id: str) -> KnowledgeSynthesis:
        synthesis = db.query(KnowledgeSynthesis).filter(KnowledgeSynthesis.id == synthesis_id).first()
        if synthesis is None:
            raise ValueError("知识综合文档不存在")
        if synthesis.status not in {"draft", "review"}:
            raise ValueError(f"当前状态不能发布: {synthesis.status}")

        created = await self.kg_service.create_entity(
            name=synthesis.id,
            entity_type="KnowledgeSynthesis",
            properties={
                "id": synthesis.id,
                "title": synthesis.title,
                "topic": synthesis.topic,
                "content": synthesis.content,
                "summary": synthesis.summary,
                "source_document_ids": synthesis.source_document_ids,
                "source_claim_ids": synthesis.source_claim_ids,
                "iteration": synthesis.iteration,
                "quality_score": synthesis.quality_score,
                "status": "published",
                "created_at": synthesis.created_at.isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
            },
        )
        if not created:
            raise RuntimeError("知识综合文档写入 Neo4j 失败")
        for article_id in synthesis.source_document_ids:
            linked = await self.kg_service.link_article_to_entity(article_id, synthesis.id, 1.0)
            if not linked:
                raise RuntimeError(f"知识综合文档来源关联失败: {article_id}")
        synthesis.status = "published"
        synthesis.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(synthesis)
        return synthesis

    async def _load_knowledge_points(self, article_ids: List[str]) -> List[Dict[str, Any]]:
        rows = await self.kg_service.execute(
            """
            MATCH (n:Entity)
            WHERE n.entity_type = 'KnowledgePoint'
              AND n.article_id IN $article_ids
            RETURN n
            LIMIT 500
            """,
            {"article_ids": article_ids},
        )
        points = []
        for row in rows if isinstance(rows, list) else []:
            node = row.get("n") if isinstance(row, dict) else None
            if node:
                points.append(dict(node))
        return points

    async def _load_prior_syntheses(self, topic: str) -> List[Dict[str, Any]]:
        if not hasattr(self.kg_service, "search_knowledge_syntheses"):
            return []
        try:
            return await self.kg_service.search_knowledge_syntheses(topic, limit=5)
        except Exception as exc:
            logger.warning("读取历史综合文档失败: %s", exc)
            return []

    @staticmethod
    def _format_prior_context(syntheses: List[Dict[str, Any]]) -> str:
        return "\n\n".join(
            f"历史文档 {item.get('id')} | 版本={item.get('iteration', 1)} | "
            f"更新时间={item.get('updated_at', '')}\n"
            f"摘要={item.get('summary', '')}\n内容={str(item.get('content', ''))[:4000]}"
            for item in syntheses
        )

    @staticmethod
    def _format_context(points: List[Dict[str, Any]], articles: List[Article]) -> str:
        lines = []
        for index, point in enumerate(points, start=1):
            evidence = point.get("evidence") or []
            if isinstance(evidence, str):
                evidence = [evidence]
            lines.append(
                f"声明{index} | id={point.get('id')} | article_id={point.get('article_id')} | "
                f"类型={point.get('category', 'unknown')} | 标题={point.get('title') or point.get('name')}\n"
                f"内容={point.get('content', '')}\n证据={'；'.join(evidence[:3])}"
            )
        if not lines:
            lines = [
                f"文章 {article.id} | 标题={article.title}\n摘要={article.summary or article.content[:500]}"
                for article in articles
            ]
        return "\n\n".join(lines)[:30000]

    async def _generate(
        self,
        topic: str,
        context: str,
        points: List[Dict[str, Any]],
        articles: List[Article],
    ) -> Dict[str, Any]:
        if self.llm_client:
            prompt = template_manager.render_template(
                self.PROMPT_VERSION.split(":")[0],
                {"topic": topic, "knowledge_points": context},
            )
            try:
                response = await self.llm_client.non_stream_chat(
                    model_id=None,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=3000,
                )
                parsed = self._parse_response(response)
                if parsed:
                    parsed["model_name"] = getattr(self.llm_client, "default_model", None)
                    return parsed
            except Exception as exc:
                logger.warning("知识综合 LLM 生成失败，使用保守草稿: %s", exc)

        title = topic.strip() or "知识综合文档"
        summary = f"基于 {len(articles)} 篇来源文章和 {len(points)} 条知识声明生成的待审核综合文档。"
        content = (
            f"# {title}\n\n## 当前资料\n{context}\n\n"
            "## 结论状态\n以上内容为来源资料整理结果，尚未完成冲突审核，不应视为最终结论。"
        )
        return {"title": title, "summary": summary, "content": content, "quality_score": 0.4}

    @staticmethod
    def _parse_response(response: str) -> Optional[Dict[str, Any]]:
        if not response or response.startswith("[错误]"):
            return None
        match = response.strip()
        if "{" in response and "}" in response:
            match = response[response.find("{"): response.rfind("}") + 1]
        try:
            payload = json.loads(match)
        except (TypeError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict) or not payload.get("content"):
            return None
        try:
            quality = max(0.0, min(1.0, float(payload.get("quality_score", 0.5))))
        except (TypeError, ValueError):
            quality = 0.5
        return {
            "title": str(payload.get("title") or "知识综合文档").strip(),
            "summary": str(payload.get("summary") or "").strip(),
            "content": str(payload["content"]).strip(),
            "quality_score": quality,
        }
