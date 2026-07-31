# -*- coding: utf-8 -*-
"""
测试微信公众号文章爬取 - 查看实际返回内容
"""

import asyncio
from playwright.async_api import async_playwright


async def test_crawl():
    """测试爬取"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 测试直接访问文章
        print("\n访问文章...")
        url = "https://mp.weixin.qq.com/s/5FW4FGwN8IjQVJHF2nldzw"
        await page.goto(url, wait_until="networkidle", timeout=30000)

        # 获取页面内容
        content = await page.content()
        print(f"页面长度: {len(content)} 字符")

        # 保存HTML到文件
        with open("test_page.html", "w", encoding="utf-8") as f:
            f.write(content)
        print("HTML已保存到 test_page.html")

        # 检查关键元素
        selectors = [
            "#activity-name",  # 文章标题
            "#js_content",     # 文章内容
            "#js_name",        # 公众号名称
            ".weui-msg",       # 错误消息
            "#js_pc_qr_code",  # PC二维码
        ]

        for sel in selectors:
            elem = await page.query_selector(sel)
            if elem:
                text = await elem.text_content()
                print(f"找到 {sel}: {text[:50] if text else '(空)'}...")
            else:
                print(f"未找到 {sel}")

        # 检查是否有二维码（需要扫码）
        qr = await page.query_selector("#js_pc_qr_code")
        if qr:
            print("\n检测到需要扫码验证！")
            print("需要获取Cookie才能继续。")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(test_crawl())
