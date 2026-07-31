# -*- coding: utf-8 -*-
"""
测试真实微信文章爬取 - 保存页面内容
"""

import asyncio
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

        # 直接使用已知的真实链接
        url = "https://mp.weixin.qq.com/s?src=11&timestamp=1785380018&ver=6873&signature=MawppIt5Tek15TufFYnuLl5682H*S25zTSzIGR0DM5BupEObipeNlSSrsAim29VG9g1eCQMVzLJw6srOqt1*Nm7Z-MtjBg7W8rslF6ClNr4355VNuuw3uY9XiP9-raSS&new=1"

        print(f"访问文章: {url}")
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 保存HTML
        content = await page.content()
        with open("real_article.html", "w", encoding="utf-8") as f:
            f.write(content)
        print(f"页面长度: {len(content)} 字符")
        print("HTML已保存到 real_article.html")

        # 检查关键元素
        selectors = [
            "#activity-name",
            "#js_content",
            "#js_name",
            ".weui-msg",
            "#js_pc_qr_code",
            ".rich_media_title",
            ".rich_media_content",
        ]

        for sel in selectors:
            elem = await page.query_selector(sel)
            if elem:
                text = await elem.text_content()
                if text:
                    print(f"找到 {sel}: {text[:80]}...")
                else:
                    print(f"找到 {sel}: (空)")
            else:
                print(f"未找到 {sel}")

        # 检查页面标题
        title = await page.title()
        print(f"\n页面标题: {title}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_real_crawl())
