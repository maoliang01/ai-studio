from sqlalchemy.dialects import postgresql

from app.api.articles import _article_search_condition, _split_article_search_terms


def compile_condition(value: str) -> str:
    return str(
        _article_search_condition(value).compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )


def test_article_search_only_uses_title_and_extracted_keywords():
    sql = compile_condition("AI")

    assert "articles.title" in sql
    assert "keywords.name" in sql
    assert "articles.content" not in sql
    assert "articles.summary" not in sql
    assert "articles.url" not in sql
    assert "scrape_sources" not in sql


def test_article_search_escapes_like_wildcards():
    sql = compile_condition("AI_100%")

    assert r"AI\\_100\\%" in sql


def test_article_search_splits_multiple_terms_as_or_conditions():
    sql = compile_condition("AI  人工智能，算力")

    assert "%AI%" in sql
    assert "%人工智能%" in sql
    assert "%算力%" in sql
    assert " OR " in sql
    assert sql.count("articles.title") == 3
    assert sql.count("keywords.name") == 3


def test_article_search_terms_are_deduplicated_case_insensitively():
    assert _split_article_search_terms("AI ai，人工智能；人工智能") == ["AI", "人工智能"]
