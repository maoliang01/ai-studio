# -*- coding: utf-8 -*-
"""
测试真实微信文章爬取

通过搜狗搜索获取真实链接后爬取
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def test_real_crawl():
    """测试爬取真实文章"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1. 搜索获取真实链接
        print("搜索秋叶AIPPT的文章...")
        search_url = "https://weixin.sogou.com/weixin?type=2&query=秋叶AIPPT"
        await page.goto(search_url, wait_until="networkidle", timeout=30000)

        # 获取第一个结果的链接
        first_result = await page.query_selector(".news-list li h3 a")
        if not first_result:
            print("未找到搜索结果")
            await browser.close()
            return

        href = await first_result.get_attribute("href")
        title = await first_result.text_content()
        print(f"找到文章: {title.strip()}")
        print(f"搜狗链接: {href}")

        # 2. 跟踪搜狗重定向获取真实链接
        print("\n跟踪重定向获取真实链接...")
        if href.startswith("/link"):
            href = "https://weixin.sogou.com" + href

        # 跟踪重定向
        response = await page.goto(href, wait_until="networkidle", timeout=30000)
        real_url = page.url
        print(f"真实链接: {real_url}")

        # 检查是否是微信文章
        if "mp.weixin.qq.com" in real_url:
            print("成功获取微信文章链接！")

            # 3. 爬取文章内容
            print("\n开始爬取文章内容...")
            await page.wait_for_selector("#activity-name", timeout=10000)

            title = await page.query_selector("#activity-name")
            if title:
                title_text = await title.text_content()
                print(f"文章标题: {title_text.strip()}")

            content = await page.query_selector("#js_content")
            if content:
                content_text = await content.text_content()
                print(f"内容长度: {len(content_text)} 字符")
                print(f"内容预览: {content_text[:200]}...")

            # 获取公众号名称
            name = await page.query_selector("#js_name")
            if name:
                name_text = await name.text_content()
                print(f"公众号: {name_text.strip()}")

            print("\n爬取成功！")
        else:
            print(f"链接不是微信文章: {real_url}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_real_crawl())
