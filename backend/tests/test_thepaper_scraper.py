import json

import pytest

from app.services.scraper import DateExtractor, ScrapeOptions, WebScraper


def make_scraper() -> WebScraper:
    scraper = WebScraper.__new__(WebScraper)
    scraper._cancel_event = None
    scraper._progress_callback = None
    scraper._use_alternate = False
    scraper._use_crawl4ai = False
    scraper._llm_service = None
    return scraper


def test_background_options_disable_llm_metadata():
    options = ScrapeOptions.for_background_task(timeout=17)

    assert options.timeout == 17
    assert options.extract_metadata is False


def test_thepaper_detail_uses_mobile_url():
    scraper = make_scraper()

    assert scraper._is_thepaper_url("https://www.thepaper.cn/channel_25951")
    assert scraper._is_thepaper_url("https://m.thepaper.cn/newsDetail_forward_123")
    assert not scraper._is_thepaper_url("https://example.com/newsDetail_forward_123")
    assert not scraper._is_thepaper_url("https://notthepaper.cn/newsDetail_forward_123")
    assert scraper._is_thepaper_listing_url("https://www.thepaper.cn/channel_25951")
    assert scraper._is_thepaper_listing_url("https://www.thepaper.cn/list_25488")
    assert not scraper._is_thepaper_listing_url("https://www.thepaper.cn/newsDetail_forward_123")
    assert (
        scraper._thepaper_mobile_url(
            "https://www.thepaper.cn/newsDetail_forward_123?commTag=true"
        )
        == "https://m.thepaper.cn/newsDetail_forward_123"
    )


def test_extract_thepaper_mobile_detail_content():
    scraper = make_scraper()
    html = """
    <html>
      <head><meta property="og:title" content="测试财经新闻"></head>
      <body>
        <h1>测试财经新闻</h1>
        <div>澎湃新闻记者 张三</div>
        <time>2026-08-05 09:30</time>
        <article>
          <p>这是第一段正文，包含足够的信息用于验证正文抽取逻辑。</p>
          <p>这是第二段正文，确保不会把页面导航误认为新闻内容。</p>
        </article>
        <div>责任编辑：李四</div>
      </body>
    </html>
    """

    title, content, published_at, author = scraper._extract_thepaper_detail_content(html)

    assert title == "测试财经新闻"
    assert "第一段正文" in content
    assert "第二段正文" in content
    assert published_at == "2026-08-05"
    assert author == "澎湃新闻记者 张三"


def test_extract_thepaper_channel_links_keeps_dom_order():
    scraper = make_scraper()
    html = """
    <a href="/newsDetail_forward_101">第一篇</a>
    <a href="/newsDetail_forward_102?from=channel">第二篇</a>
    <a href="/newsDetail_forward_101">第一篇重复链接</a>
    """

    assert scraper._extract_links_from_html(
        html, "https://www.thepaper.cn/channel_25951"
    ) == [
        "https://www.thepaper.cn/newsDetail_forward_101",
        "https://www.thepaper.cn/newsDetail_forward_102?from=channel",
    ]


def test_external_api_helpers_parse_wrapped_json_and_html():
    scraper = make_scraper()
    wrapped = 'var XinhuammNews = {"topic":"测试标题","content":"<p>第一段</p>"};'

    assert scraper._extract_javascript_json(wrapped)["topic"] == "测试标题"
    assert scraper._html_fragment_to_text(
        '<script>bad()</script><p>第一段正文</p><p>第二段正文</p>'
    ) == "第一段正文\n第二段正文"
    assert scraper._normalize_api_date(1785859200000) == "2026-08-05"


@pytest.mark.asyncio
async def test_people_share_page_uses_public_article_api(monkeypatch):
    scraper = make_scraper()
    calls = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "code": 0,
                "item": {
                    "title": "人民网测试文章",
                    "content": "<p>这是第一段完整正文。</p><p>这是第二段完整正文。</p>",
                    "date": "2026-08-05 10:00:00",
                    "source": "人民网",
                },
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            calls.append(url)
            return FakeResponse()

    monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", FakeClient)
    result = await scraper._scrape_known_external_fast(
        "http://app.people.cn/h5/detail/normal/6947657687106560",
        ScrapeOptions(timeout=10),
    )

    assert calls == ["https://api-app.people.cn/api/v2/articles/detail/6947657687106560"]
    assert result["success"] is True
    assert result["title"] == "人民网测试文章"
    assert "第二段完整正文" in result["content"]
    assert result["metadata"]["published_at"] == "2026-08-05"


@pytest.mark.asyncio
async def test_xinhua_share_page_uses_signed_article_api(monkeypatch):
    scraper = make_scraper()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            data = {
                "topic": "新华社测试文章",
                "content": "<p>这是新华社第一段完整正文。</p><p>这是新华社第二段完整正文。</p>",
                "releasedate": "2026-08-04 09:00:00",
                "docSource": "新华社",
            }
            return {"code": "0", "data": f"var XinhuammNews ={json.dumps(data, ensure_ascii=False)};"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            captured["headers"] = kwargs.get("headers", {})

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url):
            captured["url"] = url
            return FakeResponse()

    monkeypatch.setattr("app.services.scraper.httpx.AsyncClient", FakeClient)
    result = await scraper._scrape_known_external_fast(
        "https://h.xinhuaxmt.com/vh512/share/13226342?newstype=1001",
        ScrapeOptions(timeout=10),
    )

    assert captured["url"].endswith("/1017/n/newsapi/h5/news-detail/13226342")
    assert captured["headers"]["Timestamp"]
    assert captured["headers"]["Signature"]
    assert result["success"] is True
    assert result["title"] == "新华社测试文章"
    assert result["metadata"]["published_at"] == "2026-08-04"


@pytest.mark.asyncio
async def test_cctv_app_only_share_page_stops_generic_retries():
    scraper = make_scraper()

    result = await scraper._scrape_known_external_fast(
        "https://content-static.cctvnews.cctv.com/snow-book/index.html?item_id=12345",
        ScrapeOptions(timeout=10),
    )

    assert result["success"] is False
    assert result["terminal"] is True
    assert result["error"] == "publisher_app_only"


def test_extract_thepaper_list_items_uses_structured_external_links():
    html = """
    <script id="__NEXT_DATA__" type="application/json">
      {"props":{"pageProps":{"data":{"list":[
        {"contId":"101","link":"https://news.example.com/share/101",
         "name":"第一篇","pubTimeLong":1785924297606},
        {"contId":"102","link":"","name":"第二篇","pubTimeLong":1785837897606}
      ]}}}}
    </script>
    """

    links, dates, titles = DateExtractor.extract_thepaper_list_items(
        html, "https://www.thepaper.cn/list_25488"
    )

    assert links == [
        "https://news.example.com/share/101",
        "https://www.thepaper.cn/newsDetail_forward_102",
    ]
    assert dates[links[0]] == "2026-08-05"
    assert titles[links[0]] == "第一篇"


def test_trusted_thepaper_external_link_is_not_removed_by_share_filter():
    scraper = make_scraper()
    link = "https://news.example.com/share/101?share_to=copy"

    assert scraper._filter_article_links(
        [link],
        "https://www.thepaper.cn/list_25488",
        trusted_list_urls={link},
    ) == [link]


@pytest.mark.asyncio
async def test_thepaper_fast_path_never_waits_for_llm(monkeypatch):
    scraper = make_scraper()
    content = "这是澎湃财经新闻正文。" * 20

    async def fake_fast_scrape(*args, **kwargs):
        return {
            "success": True,
            "content": content,
            "markdown": content,
            "title": "测试财经新闻",
            "links": [],
            "html": "<html><body><article>测试正文</article></body></html>",
            "metadata": {"published_at": "2026-08-05", "author": "测试记者"},
        }

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("The Paper fast path must not call the LLM")

    monkeypatch.setattr(scraper, "_scrape_thepaper_fast", fake_fast_scrape)
    monkeypatch.setattr(scraper, "_extract_metadata_with_llm", fail_if_called)
    monkeypatch.setattr(scraper, "_extract_style_with_llm", fail_if_called)

    result = await scraper.scrape(
        "https://www.thepaper.cn/newsDetail_forward_123",
        ScrapeOptions(timeout=10, extract_metadata=True),
    )

    assert result.status == "success"
    assert result.summary
    assert result.published_at == "2026-08-05"
