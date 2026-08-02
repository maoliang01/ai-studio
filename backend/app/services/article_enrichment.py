"""文章元数据的确定性补全工具。"""

import re
from typing import Any, Dict, List

from app.services.scraper import extract_keywords_locally, summarize_locally


def infer_article_author(title: str, source_name: str = "") -> str:
    """优先从站点标题后缀识别发布机构，再回退到信源名称。"""
    normalized_title = (title or "").strip()
    match = re.search(r"(?:--|——)\s*([^\-—]{2,100})\s*$", normalized_title)
    if match:
        return match.group(1).strip()
    return (source_name or "").strip()


def build_article_enrichment(article: Any) -> Dict[str, Any]:
    """只为缺失字段生成补充值，不覆盖已有人工或模型结果。"""
    title = article.title or ""
    content = article.content or ""
    source_name = article.source.name if getattr(article, "source", None) else ""
    changes: Dict[str, Any] = {}

    if not (article.summary or "").strip() and content.strip():
        summary = summarize_locally(content)
        if summary:
            changes["summary"] = summary

    if not (article.author or "").strip():
        author = infer_article_author(title, source_name)
        if author:
            changes["author"] = author

    current_keywords: List[str] = [
        link.keyword.name
        for link in getattr(article, "keywords", [])
        if link.keyword and link.keyword.name
    ]
    if not current_keywords and (title.strip() or content.strip()):
        keywords = extract_keywords_locally(title, content)
        if keywords:
            changes["keywords"] = keywords

    if not article.word_count and content:
        changes["word_count"] = len(re.sub(r"\s+", "", content))

    return changes
