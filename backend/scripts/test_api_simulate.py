# -*- coding: utf-8 -*-
"""
模拟API调用测试
"""

import asyncio
import sys
sys.path.insert(0, '.')

from app.core.database import get_session_local
from app.services.wechat.pipeline import WechatPipeline


async def test():
    """测试"""
    SessionLocal = get_session_local()
    db = SessionLocal()

    try:
        pipeline = WechatPipeline(db)

        url = "https://mp.weixin.qq.com/s/test123"
        print(f"测试爬取: {url}")

        result = await pipeline.process_article(url)
        print(f"结果: {result}")

    except Exception as e:
        print(f"异常: {e}")
        print(f"异常类型: {type(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test())
