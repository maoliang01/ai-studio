# -*- coding: utf-8 -*-
"""
直接测试API - 禁用代理
"""

import asyncio
import httpx


async def test_api():
    """测试API"""
    url = "https://mp.weixin.qq.com/s?src=11&timestamp=1785380120&ver=6873&signature=SBcjDNjFNlbJJTLHexabBi9UQVbjxeWbVurIpkElgdK2E--*Im6PCszRCQvLNdx1bW1YvETJhwJJR4ys6d15fjXPglm2RhLbOX2MkWeHAE0Ij5-xeUxfKT8etqnzaTCN&new=1"

    print(f"测试爬取: {url}")

    # 禁用代理
    async with httpx.AsyncClient(proxy=None) as client:
        # 测试API
        response = await client.post(
            "http://localhost:8084/api/wechat/crawl/article",
            params={"url": url},
            timeout=120
        )

        print(f"状态码: {response.status_code}")
        print(f"响应: {response.text}")


if __name__ == "__main__":
    asyncio.run(test_api())
