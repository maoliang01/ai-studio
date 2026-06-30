# Firecrawl 本地部署调用示例
# 访问地址: http://localhost:3002

from firecrawl import Firecrawl
import json

# 初始化客户端（连接本地部署，不需要 API Key）
app = Firecrawl(
    api_key="",  # 本地部署不需要 API Key
    api_url="http://localhost:3002"  # 本地服务地址
)

def test_scrape():
    """抓取单个网页"""
    print("📄 测试网页抓取...")
    try:
        doc = app.scrape("https://example.com", formats=["markdown"])
        print(f"✅ 标题: {doc.metadata.title if hasattr(doc.metadata, 'title') else doc.metadata}")
        print(f"📝 内容长度: {len(doc.markdown)} 字符")
        print(f"内容预览: {doc.markdown[:200]}...")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
    print()

def test_crawl():
    """爬取网站"""
    print("🕷️ 测试网站爬取...")
    try:
        # 限制爬取 3 个页面
        docs = app.crawl("https://example.com", limit=3)
        print(f"✅ 爬取了 {len(docs)} 个页面")
        for doc in docs:
            print(f"  - {doc.metadata.get('title', 'N/A')}")
    except Exception as e:
        print(f"❌ 爬取失败: {e}")
    print()

def test_search():
    """搜索网页"""
    print("🔍 测试搜索功能...")
    try:
        # 搜索需要配置 SearXNG 或 Google API
        # 注意：本地部署默认使用 Google 搜索，可能需要 API Key
        results = app.search("Python web scraping", limit=3)
        print(f"✅ 找到 {len(results.data)} 个结果")
        if results.data:
            for r in results.data:
                print(f"  - {r.title}")
    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        print("  提示: 搜索功能需要配置 SearXNG 或 Google Search API")
    print()

def test_map():
    """获取网站地图"""
    print("🗺️ 测试网站地图...")
    try:
        result = app.map("https://example.com")
        print(f"✅ 发现 {len(result.links)} 个链接")
        if result.links:
            print(f"  示例链接: {result.links[:3]}")
    except Exception as e:
        print(f"❌ 地图获取失败: {e}")
    print()

if __name__ == "__main__":
    print("=" * 50)
    print("🔥 Firecrawl 本地部署测试")
    print("=" * 50)
    print()

    test_scrape()
    # test_crawl()  # 取消注释以测试爬取功能
    # test_search()  # 取消注释以测试搜索功能
    # test_map()  # 取消注释以测试地图功能

    print("=" * 50)
    print("✅ 测试完成!")
    print("=" * 50)