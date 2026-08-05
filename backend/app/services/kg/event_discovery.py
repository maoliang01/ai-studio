"""从已有文章和知识点中发现值得关注的候选事件。"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.models.article import Article


class EventDiscoveryService:
    """基于近期文档信号生成候选事件，不要求用户预先输入主题。"""

    EVENT_MARKERS = (
        "发布", "获批", "突破", "完成", "签约", "启动", "建成", "上线",
        "增长", "下降", "投资", "计划", "试验", "发现", "合作", "入选",
    )

    @staticmethod
    def _tokens(text: str) -> set[str]:
        words = set(re.findall(r"[A-Za-z0-9+#.-]{2,}|[\u4e00-\u9fff]{2}", text or ""))
        compact = re.sub(r"[^\u4e00-\u9fff]", "", text or "")
        words.update(compact[index:index + 2] for index in range(max(0, len(compact) - 1)))
        return {word for word in words if len(word) >= 2}

    def discover(self, db: Session, limit: int = 20, days: int = 90) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(days=max(1, min(days, 3650)))
        articles = db.query(Article).filter(
            Article.status.in_(["completed", "success"]),
            Article.scraped_at >= cutoff,
        ).order_by(Article.scraped_at.desc()).limit(300).all()
        if not articles:
            articles = db.query(Article).filter(
                Article.status.in_(["completed", "success"]),
            ).order_by(Article.scraped_at.desc()).limit(100).all()

        candidates = []
        article_tokens = {article.id: self._tokens(f"{article.title} {article.summary}") for article in articles}
        for article in articles:
            title = (article.title or "").strip()
            if len(title) < 4:
                continue
            base_tokens = article_tokens[article.id]
            related = []
            for other in articles:
                if other.id == article.id:
                    continue
                other_tokens = article_tokens[other.id]
                shared = base_tokens & other_tokens
                union = base_tokens | other_tokens
                similarity = len(shared) / len(union) if union else 0
                if len(shared) >= 2 and similarity >= 0.16:
                    related.append((similarity, other))
            related.sort(key=lambda item: (item[0], item[1].scraped_at or datetime.min), reverse=True)
            evidence_articles = [article] + [item[1] for item in related[:7]]
            marker_hits = [marker for marker in self.EVENT_MARKERS if marker in title]
            evidence_text = (article.summary or article.content or "").strip()
            signal = 0.35 + min(0.25, len(marker_hits) * 0.08) + min(0.3, len(evidence_articles) * 0.08)
            age_days = max(0, (datetime.utcnow() - (article.scraped_at or datetime.utcnow())).days)
            signal += max(0, 0.25 - age_days / 365)
            candidate_id = "event-" + hashlib.sha256(article.id.encode("utf-8")).hexdigest()[:24]
            candidates.append({
                "id": candidate_id,
                "title": title,
                "topic": title,
                "confidence": round(min(signal, 0.95), 4),
                "signal_type": "cross_document" if len(evidence_articles) > 1 else ("event_marker" if marker_hits else "recent_article"),
                "signal_reasons": (marker_hits or ["近期出现的新文档"]) + ([f"{len(evidence_articles)}篇相关文档交叉印证"] if len(evidence_articles) > 1 else ["证据不足：仅1篇文档"]),
                "evidence_articles": [{
                    "id": source.id,
                    "title": source.title,
                    "summary": (source.summary or source.content or "")[:300],
                    "published_at": source.published_at.isoformat() if source.published_at else None,
                    "scraped_at": source.scraped_at.isoformat() if source.scraped_at else None,
                    "url": source.url,
                } for source in evidence_articles],
                "discovered_at": datetime.utcnow().isoformat(),
            })
        candidates.sort(key=lambda item: (item["confidence"], item["evidence_articles"][0]["scraped_at"] or ""), reverse=True)
        return candidates[:max(1, min(limit, 100))]
