# -*- coding: utf-8 -*-
"""
获取微信公众号 Cookie

使用 Playwright 打开微信公众号平台，等待用户扫码后保存 Cookie
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def get_cookie():
    """获取微信公众号 Cookie"""
    print("正在启动浏览器...")

    async with async_playwright() as p:
        # 有头模式，方便用户扫码
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 访问微信公众号平台
        print("正在打开微信公众号平台...")
        await page.goto("https://mp.weixin.qq.com/")

        print("\n" + "=" * 50)
        print("请在浏览器中登录微信公众号平台")
        print("登录成功后，请回到此窗口按 Enter 键继续")
        print("=" * 50 + "\n")

        # 等待用户登录
        input("按 Enter 键继续...")

        # 获取 Cookie
        cookies = await context.cookies()

        # 保存到文件
        output_file = Path(__file__).parent / "wechat_cookie.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        print(f"\nCookie 已保存到: {output_file}")
        print(f"Cookie 数量: {len(cookies)}")

        # 打印关键 Cookie
        key_cookies = [c for c in cookies if c["name"] in ["slave_sid", "slave_user", "bizuin"]]
        if key_cookies:
            print("\n关键 Cookie:")
            for c in key_cookies:
                print(f"  - {c['name']}: {c['value'][:20]}...")

        await browser.close()

        return cookies


if __name__ == "__main__":
    cookies = asyncio.run(get_cookie())
    print("\n获取完成！")
