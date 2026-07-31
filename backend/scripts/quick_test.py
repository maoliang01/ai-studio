# -*- coding: utf-8 -*-
"""
快速测试爬虫
"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.core.database import get_session_local
from app.services.wechat.pipeline import WechatPipeline


async def test():
    """测试爬取"""
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        pipeline = WechatPipeline(db)

        # 测试URL
        url = "https://mp.weixin.qq.com/s?src=11&timestamp=1785380120&ver=6873&signature=SBcjDNjFNlbJJTLHexabBi9UQVbjxeWbVurIpkElgdK2E--*Im6PCszRCQvLNdx1bW1YvETJhwJJR4ys6d15fjXPglm2RhLbOX2MkWeHAE0Ij5-xeUxfKT8etqnzaTCN&new=1"

        print(f"测试爬取: {url}")
        result = await pipeline.process_article(url)
        print(f"结果: {result}")

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test())
