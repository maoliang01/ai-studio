# -*- coding: utf-8 -*-
"""
自动获取微信公众号 Cookie

使用 Playwright 打开微信公众号平台，等待用户扫码后保存 Cookie
自动导入到数据库
"""

import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright


async def get_and_save_cookie():
    """获取并保存 Cookie"""
    print("=" * 60)
    print("微信公众号 Cookie 获取工具")
    print("=" * 60)
    print("\n此工具将:")
    print("1. 打开微信公众号平台登录页面")
    print("2. 等待您扫码登录")
    print("3. 自动获取并保存 Cookie 到数据库")
    print()

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

        print("\n" + "=" * 60)
        print("请在浏览器中登录微信公众号平台")
        print("登录成功后，请回到此窗口按 Enter 键继续")
        print("=" * 60 + "\n")

        # 等待用户登录
        input("按 Enter 键继续...")

        # 获取 Cookie
        cookies = await context.cookies()
        print(f"\n获取到 {len(cookies)} 个 Cookie")

        # 转换为 JSON 字符串
        cookie_data = json.dumps(cookies, ensure_ascii=False)

        # 保存到文件备份
        output_file = Path(__file__).parent / "wechat_cookie_backup.json"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(cookie_data)
        print(f"Cookie 备份已保存到: {output_file}")

        # 调用 API 保存到数据库
        print("\n正在保存到数据库...")
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "http://localhost:8084/api/wechat/cookies",
                    json={
                        "name": "微信公众号Cookie",
                        "cookie_data": cookie_data
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    result = response.json()
                    print(f"保存成功！Cookie ID: {result.get('item', {}).get('id')}")
                else:
                    print(f"保存失败: {response.text}")
        except Exception as e:
            print(f"保存到数据库失败: {e}")
            print(f"请手动导入 Cookie，数据已保存到: {output_file}")

        await browser.close()

        # 打印关键 Cookie
        key_cookies = [c for c in cookies if c["name"] in ["slave_sid", "slave_user", "bizuin"]]
        if key_cookies:
            print("\n关键 Cookie:")
            for c in key_cookies:
                print(f"  - {c['name']}: {c['value'][:20]}...")

        return cookies


if __name__ == "__main__":
    cookies = asyncio.run(get_and_save_cookie())
    print("\n获取完成！")
    print("现在可以使用 API 测试爬取功能了。")
