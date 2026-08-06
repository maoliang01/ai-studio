"""文章元数据的确定性补全工具。"""

import re
from typing import Any, Dict, List

from app.services.scraper import extract_keywords_locally, summarize_locally


def infer_article_style_locally(title: str = "", content: str = "") -> str:
    """在文体模型未启用或不可用时，使用可解释规则保证文体字段不为空。"""
    text = f"{title or ''}\n{content or ''}".strip()
    if not text:
        return ""

    rules = (
        ("通知公告", ("通知", "公告", "公示", "通告", "招标", "征集", "申报")),
        ("会议纪要", ("会议纪要", "会议记录", "纪要")),
        ("领导讲话", ("讲话", "致辞", "发言稿", "演讲")),
        ("工作简报", ("工作简报", "工作动态", "工作进展", "简报")),
        ("政策解读", ("政策解读", "政策分析", "法规解读")),
        ("行业动态", ("行业动态", "行业趋势", "市场分析", "产业发展")),
        ("专题文章", ("研究报告", "专题", "科研", "研究", "实验", "取得进展", "发现")),
    )
    for style, markers in rules:
        if any(marker in text for marker in markers):
            return style
    return "新闻报道"


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

    if not (article.style or "").strip() and (title.strip() or content.strip()):
        changes["style"] = infer_article_style_locally(title, content)

    return changes
