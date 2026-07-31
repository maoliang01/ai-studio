# -*- coding: utf-8 -*-
"""
测试微信公众号文章爬取

尝试不登录直接爬取微信公众号文章
"""

import asyncio
import json
from playwright.async_api import async_playwright


async def test_crawl():
    """测试爬取"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        )
        page = await context.new_page()

        # 测试1: 直接访问文章
        print("\n测试1: 直接访问文章...")
        test_urls = [
            "https://mp.weixin.qq.com/s/5FW4FGwN8IjQVJHF2nldzw",  # 秋叶AIPPT的文章
            "https://mp.weixin.qq.com/s/test123",  # 不存在的文章
        ]

        for url in test_urls:
            print(f"\n尝试访问: {url}")
            try:
                response = await page.goto(url, wait_until="networkidle", timeout=30000)
                print(f"  状态码: {response.status}")

                # 检查是否有文章内容
                title = await page.title()
                print(f"  标题: {title}")

                # 检查是否有活动名称（文章标题）
                activity_name = await page.query_selector("#activity-name")
                if activity_name:
                    text = await activity_name.text_content()
                    print(f"  文章标题: {text.strip()}")
                else:
                    print("  未找到文章标题")

                # 检查是否有内容
                content = await page.query_selector("#js_content")
                if content:
                    text = await content.text_content()
                    print(f"  内容长度: {len(text)} 字符")
                else:
                    print("  未找到文章内容")

            except Exception as e:
                print(f"  错误: {e}")

        # 测试2: 搜索公众号
        print("\n\n测试2: 搜索公众号...")
        search_url = "https://mp.weixin.qq.com/cgi-bin/searchbiz?action=search_biz&begin=0&count=5&query=秋叶AIPPT&token=&lang=zh_CN&f=json&ajax=1"
        try:
            response = await page.goto(search_url, wait_until="networkidle", timeout=30000)
            print(f"  状态码: {response.status}")
            content = await page.content()
            print(f"  内容长度: {len(content)} 字符")
        except Exception as e:
            print(f"  错误: {e}")

        await browser.close()
        print("\n测试完成！")


if __name__ == "__main__":
    asyncio.run(test_crawl())
