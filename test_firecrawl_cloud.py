# Firecrawl 云端 & 本地调用示例
# 使用前请设置环境变量或直接填入 API Key

# ================================================
# 配置区域
# ================================================

# 模式选择: "local" 或 "cloud"
MODE = "local"  # 改为 "cloud" 使用云端服务

# 本地部署地址（默认）
LOCAL_URL = "http://localhost:3002"

# 云端 API Key（从 https://firecrawl.dev 获取）
CLOUD_API_KEY = "fc-your-api-key-here"  # ⬅️ 填入你的 API Key

# 云端 API 地址
CLOUD_URL = "https://api.firecrawl.dev"


# ================================================
# 初始化客户端
# ================================================

from firecrawl import Firecrawl

def get_client():
    """根据模式获取 Firecrawl 客户端"""
    if MODE == "cloud":
        if not CLOUD_API_KEY or CLOUD_API_KEY == "fc-your-api-key-here":
            raise ValueError("请先设置 CLOUD_API_KEY！")
        return Firecrawl(
            api_key=CLOUD_API_KEY,
            api_url=CLOUD_URL
        )
    else:
        return Firecrawl(
            api_key="",  # 本地部署不需要 API Key
            api_url=LOCAL_URL
        )


# ================================================
# 示例函数
# ================================================

def test_scrape():
    """抓取单个网页"""
    print(f"\n{'='*50}")
    print(f"🔍 抓取网页 (模式: {MODE.upper()})")
    print('='*50)

    app = get_client()

    try:
        # 抓取网页
        doc = app.scrape(
            "https://example.com",
            formats=["markdown"]
        )

        # 提取内容
        if hasattr(doc, 'markdown') and doc.markdown:
            content = doc.markdown
        elif hasattr(doc, 'content') and doc.content:
            content = doc.content
        else:
            content = "无内容"

        print(f"✅ 抓取成功!")
        print(f"📝 字数: {len(content.replace(chr(10),''))}")
        print(f"\n内容预览:\n{content[:500]}...")

    except Exception as e:
        print(f"❌ 抓取失败: {e}")


def test_map():
    """获取网站地图"""
    print(f"\n{'='*50}")
    print(f"🗺️ 获取网站地图 (模式: {MODE.upper()})")
    print('='*50)

    app = get_client()

    try:
        result = app.map("https://example.com")

        links = getattr(result, 'links', []) or []
        print(f"✅ 发现 {len(links)} 个链接")

        if links:
            print("\n前 5 个链接:")
            for i, link in enumerate(links[:5], 1):
                print(f"  {i}. {link}")

    except Exception as e:
        print(f"❌ 获取地图失败: {e}")


def test_crawl():
    """爬取网站（深度爬取）"""
    print(f"\n{'='*50}")
    print(f"🕷️ 深度爬取网站 (模式: {MODE.upper()})")
    print('='*50)

    app = get_client()

    try:
        print("开始爬取 (限制 3 个页面)...")
        docs = app.crawl("https://example.com", limit=3)

        print(f"✅ 爬取了 {len(docs) if docs else 0} 个页面")

        if docs:
            for i, doc in enumerate(docs[:3], 1):
                title = getattr(doc, 'title', '') or getattr(doc, 'metadata', {}).get('title', '无标题')
                print(f"  {i}. {title}")

    except Exception as e:
        print(f"❌ 爬取失败: {e}")


def test_search():
    """搜索网页（仅云端可用）"""
    print(f"\n{'='*50}")
    print(f"🔎 搜索功能 (模式: {MODE.upper()})")
    print('='*50)

    if MODE != "cloud":
        print("ℹ️ 搜索功能仅云端服务可用，请切换到 cloud 模式")
        return

    app = get_client()

    try:
        results = app.search("Python web scraping", limit=5)

        data = getattr(results, 'data', []) or []
        print(f"✅ 找到 {len(data)} 个结果")

        for i, r in enumerate(data[:5], 1):
            title = getattr(r, 'title', '无标题')
            url = getattr(r, 'url', '')
            print(f"  {i}. {title}")
            print(f"     {url}")

    except Exception as e:
        print(f"❌ 搜索失败: {e}")


# ================================================
# 主程序
# ================================================

if __name__ == "__main__":
    print("🔥 Firecrawl 调用示例")
    print(f"当前模式: {MODE.upper()}")
    print(f"API 地址: {CLOUD_URL if MODE == 'cloud' else LOCAL_URL}")

    print("\n可用功能:")
    print("  1. 抓取单个网页 (scrape)")
    print("  2. 获取网站地图 (map)")
    print("  3. 深度爬取网站 (crawl)")
    print("  4. 搜索网页 (search, 仅云端)")

    # 测试所有功能
    test_scrape()
    test_map()

    if MODE == "cloud":
        test_crawl()
        test_search()