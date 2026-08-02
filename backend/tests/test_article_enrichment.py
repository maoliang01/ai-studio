from types import SimpleNamespace

from app.services.article_enrichment import (
    build_article_enrichment,
    infer_article_author,
)


def test_infer_article_author_from_title_suffix():
    assert infer_article_author(
        "新闻标题--中国科学院空天信息创新研究院",
        "动态新闻",
    ) == "中国科学院空天信息创新研究院"


def test_build_article_enrichment_only_fills_missing_fields():
    article = SimpleNamespace(
        title="空天院开展遥感培训--中国科学院空天信息创新研究院",
        content="空天院组织开展遥感技术培训。培训聚焦卫星遥感应用与科研实践。",
        summary="",
        author=None,
        word_count=0,
        source=SimpleNamespace(name="空天院动态新闻"),
        keywords=[],
    )

    changes = build_article_enrichment(article)

    assert changes["summary"]
    assert changes["author"] == "中国科学院空天信息创新研究院"
    assert changes["keywords"]
    assert changes["word_count"] > 0


def test_build_article_enrichment_preserves_existing_values():
    article = SimpleNamespace(
        title="标题",
        content="正文内容足够用于测试。",
        summary="人工摘要",
        author="人工作者",
        word_count=10,
        source=None,
        keywords=[SimpleNamespace(keyword=SimpleNamespace(name="现有关键词"))],
    )

    assert build_article_enrichment(article) == {}
