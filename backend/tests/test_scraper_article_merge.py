import hashlib

from app.services.scraper import ScrapedResult, merge_scraped_result_into_article


class FakeArticle:
    def __init__(self, content: str = "old content"):
        self.id = "article-1"
        self.title = "old title"
        self.content = content
        self.html = "old html"
        self.word_count = len(content)
        self.author = "old author"
        self.summary = "old summary"
        self.style = "news"
        self.status = "success"
        self.error_message = None
        self.category_id = "category-old"
        self.source_id = "source-old"
        self.published_at = None
        self.content_hash = self.calculate_content_hash()
        self.kg_status = "success"
        self.kg_processed_at = object()
        self.kg_error_message = None

    def calculate_content_hash(self) -> str:
        return hashlib.sha256(self.content.encode()).hexdigest()


def test_repeat_save_without_source_preserves_existing_provenance():
    article = FakeArticle()
    result = ScrapedResult(
        url="https://example.com/article",
        title="new title",
        content="old content",
        status="success",
    )

    changed = merge_scraped_result_into_article(article, result)

    assert changed is False
    assert article.id == "article-1"
    assert article.source_id == "source-old"
    assert article.category_id == "category-old"
    assert article.kg_status == "success"


def test_repeat_save_with_explicit_source_updates_provenance_and_kg_state():
    article = FakeArticle()
    result = ScrapedResult(
        url="https://example.com/article",
        content="new content",
        status="success",
        published_at="2026-08-02",
    )

    changed = merge_scraped_result_into_article(
        article,
        result,
        category_id="category-new",
        source_id="source-new",
    )

    assert changed is True
    assert article.source_id == "source-new"
    assert article.category_id == "category-new"
    assert article.kg_status == "pending"
    assert article.kg_processed_at is None
    assert article.published_at.isoformat() == "2026-08-02"
