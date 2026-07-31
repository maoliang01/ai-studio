# -*- coding: utf-8 -*-
"""
搜索微信公众号文章

使用搜狗微信搜索查找公众号文章
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def search_articles():
    """搜索秋叶AIPPT的文章"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 使用搜狗微信搜索
        print("搜索秋叶AIPPT的文章...")
        search_url = "https://weixin.sogou.com/weixin?type=1&query=秋叶AIPPT"
        await page.goto(search_url, wait_until="networkidle", timeout=30000)

        # 获取搜索结果
        results = await page.query_selector_all(".news-list li")

        if not results:
            print("未找到搜索结果")
            # 保存页面查看
            content = await page.content()
            with open("search_result.html", "w", encoding="utf-8") as f:
                f.write(content)
            print("搜索结果页面已保存到 search_result.html")
        else:
            print(f"找到 {len(results)} 个结果")
            for i, result in enumerate(results[:5]):
                try:
                    # 获取标题
                    title_elem = await result.query_selector("h3 a")
                    if title_elem:
                        title = await title_elem.text_content()
                        href = await title_elem.get_attribute("href")
                        print(f"\n{i+1}. {title.strip()}")
                        print(f"   链接: {href}")
                except Exception as e:
                    print(f"   解析错误: {e}")

        # 也尝试搜索文章
        print("\n\n搜索文章...")
        search_url2 = "https://weixin.sogou.com/weixin?type=2&query=秋叶AIPPT"
        await page.goto(search_url2, wait_until="networkidle", timeout=30000)

        results2 = await page.query_selector_all(".news-list li")
        if results2:
            print(f"找到 {len(results2)} 篇文章")
            for i, result in enumerate(results2[:5]):
                try:
                    title_elem = await result.query_selector("h3 a")
                    if title_elem:
                        title = await title_elem.text_content()
                        href = await title_elem.get_attribute("href")
                        print(f"\n{i+1}. {title.strip()}")
                        print(f"   链接: {href}")
                except Exception as e:
                    print(f"   解析错误: {e}")

        await browser.close()
        print("\n搜索完成！")


if __name__ == "__main__":
    asyncio.run(search_articles())
