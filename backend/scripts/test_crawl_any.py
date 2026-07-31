# -*- coding: utf-8 -*-
"""
测试爬取任意微信文章

搜索并爬取可用的微信公众号文章
"""

import asyncio
from playwright.async_api import async_playwright


async def test_crawl_any():
    """搜索并爬取可用文章"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 搜索热门公众号文章
        print("搜索微信文章...")
        search_url = "https://weixin.sogou.com/weixin?type=2&query=AI工具推荐"
        await page.goto(search_url, wait_until="networkidle", timeout=30000)

        # 获取搜索结果
        results = await page.query_selector_all(".news-list li")
        print(f"找到 {len(results)} 个结果")

        # 遍历结果找到可用的文章
        for i, result in enumerate(results[:5]):
            try:
                title_elem = await result.query_selector("h3 a")
                if not title_elem:
                    continue

                title = await title_elem.text_content()
                href = await title_elem.get_attribute("href")

                print(f"\n尝试 {i+1}: {title.strip()}")
                print(f"  链接: {href}")

                # 跟踪重定向
                if href.startswith("/link"):
                    href = "https://weixin.sogou.com" + href

                response = await page.goto(href, wait_until="networkidle", timeout=30000)
                real_url = page.url
                print(f"  真实链接: {real_url}")

                if "mp.weixin.qq.com" in real_url:
                    # 等待页面加载
                    try:
                        await page.wait_for_selector("#activity-name", timeout=5000)
                        title_elem = await page.query_selector("#activity-name")
                        if title_elem:
                            title_text = await title_elem.text_content()
                            print(f"  标题: {title_text.strip()}")

                        content_elem = await page.query_selector("#js_content")
                        if content_elem:
                            content_text = await content_elem.text_content()
                            print(f"  内容长度: {len(content_text)} 字符")

                        name_elem = await page.query_selector("#js_name")
                        if name_elem:
                            name_text = await name_elem.text_content()
                            print(f"  公众号: {name_text.strip()}")

                        print("  爬取成功！")

                        # 保存到文件
                        html = await page.content()
                        with open(f"article_{i+1}.html", "w", encoding="utf-8") as f:
                            f.write(html)
                        print(f"  HTML已保存到 article_{i+1}.html")

                        break  # 找到可用文章就停止
                    except Exception as e:
                        print(f"  页面加载失败: {e}")
                else:
                    print(f"  不是微信文章")

            except Exception as e:
                print(f"  错误: {e}")

        await browser.close()
        print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_crawl_any())
