# -*- coding: utf-8 -*-
"""
微信公众号 Cookie 管理器

负责 Cookie 的导入、验证、存储和管理
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.wechat import WechatCookie

logger = logging.getLogger(__name__)


class CookieManager:
    """微信公众号 Cookie 管理器"""

    # Cookie 有效期（天）
    COOKIE_EXPIRE_DAYS = 7

    def __init__(self, db: Session):
        self.db = db

    async def create_cookie(
        self,
        name: str,
        cookie_data: str,
        expires_at: Optional[datetime] = None
    ) -> WechatCookie:
        """
        创建新的 Cookie

        Args:
            name: Cookie 名称
            cookie_data: Cookie JSON 数据
            expires_at: 过期时间

        Returns:
            WechatCookie 对象
        """
        # 验证 Cookie 格式
        parsed_cookies = self._parse_cookie_data(cookie_data)
        if not parsed_cookies:
            raise ValueError("Cookie 数据格式无效，必须是有效的 JSON 数组格式")

        # 设置默认过期时间
        if not expires_at:
            expires_at = datetime.utcnow() + timedelta(days=self.COOKIE_EXPIRE_DAYS)

        # 创建数据库记录
        self.db.query(WechatCookie).update({WechatCookie.is_active: False})
        cookie = WechatCookie(
            name=name,
            cookie_data=cookie_data,
            expires_at=expires_at,
            is_active=True
        )

        self.db.add(cookie)
        self.db.commit()
        self.db.refresh(cookie)

        logger.info(f"创建 Cookie: {name}, 过期时间: {expires_at}")
        return cookie

    async def get_cookies(
        self,
        active_only: bool = False
    ) -> List[WechatCookie]:
        """
        获取 Cookie 列表

        Args:
            active_only: 是否只返回激活状态的 Cookie

        Returns:
            Cookie 列表
        """
        query = self.db.query(WechatCookie)
        if active_only:
            query = query.filter(WechatCookie.is_active == True)
        return query.all()

    async def get_cookie(self, cookie_id: str) -> Optional[WechatCookie]:
        """
        获取单个 Cookie

        Args:
            cookie_id: Cookie ID

        Returns:
            WechatCookie 对象
        """
        return self.db.query(WechatCookie).filter(WechatCookie.id == cookie_id).first()

    async def update_cookie(
        self,
        cookie_id: str,
        name: Optional[str] = None,
        cookie_data: Optional[str] = None,
        is_active: Optional[bool] = None,
        expires_at: Optional[datetime] = None,
    ) -> Optional[WechatCookie]:
        """
        更新 Cookie

        Args:
            cookie_id: Cookie ID
            name: 新名称
            cookie_data: 新的 Cookie 数据
            is_active: 是否激活

        Returns:
            更新后的 WechatCookie 对象
        """
        cookie = await self.get_cookie(cookie_id)
        if not cookie:
            return None

        if name is not None:
            cookie.name = name
        if cookie_data is not None:
            # 验证 Cookie 格式
            parsed_cookies = self._parse_cookie_data(cookie_data)
            if not parsed_cookies:
                raise ValueError("Cookie 数据格式无效")
            cookie.cookie_data = cookie_data
            # 更新凭证代表重新登录，默认从此刻续期 7 天。
            cookie.expires_at = expires_at or (datetime.utcnow() + timedelta(days=self.COOKIE_EXPIRE_DAYS))
            self.db.query(WechatCookie).filter(WechatCookie.id != cookie.id).update({WechatCookie.is_active: False})
            cookie.is_active = True
        elif expires_at is not None:
            cookie.expires_at = expires_at
        if is_active is not None:
            cookie.is_active = is_active

        cookie.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(cookie)

        logger.info(f"更新 Cookie: {cookie_id}")
        return cookie

    async def delete_cookie(self, cookie_id: str) -> bool:
        """
        删除 Cookie

        Args:
            cookie_id: Cookie ID

        Returns:
            是否删除成功
        """
        cookie = await self.get_cookie(cookie_id)
        if not cookie:
            return False

        self.db.delete(cookie)
        self.db.commit()

        logger.info(f"删除 Cookie: {cookie_id}")
        return True

    async def activate_cookie(self, cookie_id: str) -> Optional[WechatCookie]:
        """
        激活 Cookie

        Args:
            cookie_id: Cookie ID

        Returns:
            更新后的 WechatCookie 对象
        """
        cookie = await self.get_cookie(cookie_id)
        if not cookie:
            return None
        self.db.query(WechatCookie).filter(WechatCookie.id != cookie_id).update({WechatCookie.is_active: False})
        return await self.update_cookie(cookie_id, is_active=True)

    async def deactivate_cookie(self, cookie_id: str) -> Optional[WechatCookie]:
        """
        停用 Cookie

        Args:
            cookie_id: Cookie ID

        Returns:
            更新后的 WechatCookie 对象
        """
        return await self.update_cookie(cookie_id, is_active=False)

    async def get_active_cookie(self) -> Optional[WechatCookie]:
        """
        获取当前激活且未过期的 Cookie

        Returns:
            WechatCookie 对象，如果没有可用的 Cookie 则返回 None
        """
        now = datetime.utcnow()
        cookies = self.db.query(WechatCookie).filter(
            WechatCookie.is_active == True,
            WechatCookie.expires_at > now
        ).order_by(WechatCookie.last_used_at.desc()).first()

        return cookies

    async def validate_cookie(self, cookie_id: str) -> Dict[str, Any]:
        """
        验证 Cookie 是否有效

        Args:
            cookie_id: Cookie ID

        Returns:
            验证结果字典
        """
        cookie = await self.get_cookie(cookie_id)
        if not cookie:
            return {
                "valid": False,
                "message": "Cookie 不存在"
            }

        # 检查是否过期
        if cookie.expires_at and cookie.expires_at < datetime.utcnow():
            return {
                "valid": False,
                "message": "Cookie 已过期",
                "expires_at": cookie.expires_at.isoformat()
            }

        # 尝试解析 Cookie 数据
        parsed_cookies = self._parse_cookie_data(cookie.cookie_data)
        if not parsed_cookies:
            return {
                "valid": False,
                "message": "Cookie 数据格式无效"
            }

        # 时间段文章发现依赖公众号管理后台登录态，而不是普通文章页 Cookie。
        # token 位于后台 URL 中；Cookie 中通常应包含 slave_sid，以及
        # bizuin/data_bizuin 中的至少一个。
        cookie_names = {
            str(item.get("name", ""))
            for item in parsed_cookies
            if isinstance(item, dict)
        }
        found_keys = sorted(
            cookie_names.intersection({"slave_sid", "slave_user", "bizuin", "data_bizuin", "data_ticket"})
        )
        has_backend_session = "slave_sid" in cookie_names and bool(
            {"bizuin", "data_bizuin"}.intersection(cookie_names)
        )

        return {
            "valid": has_backend_session,
            "message": (
                "公众号管理后台 Cookie 格式有效"
                if has_backend_session
                else "Cookie JSON 可解析，但不包含公众号管理后台登录凭证。请登录 mp.weixin.qq.com 后，在带 token 的管理后台页面重新导出。"
            ),
            "expires_at": cookie.expires_at.isoformat() if cookie.expires_at else None,
            "has_required_keys": has_backend_session,
            "found_keys": found_keys
        }

    def _parse_cookie_data(self, cookie_data: str) -> Optional[List[Dict[str, Any]]]:
        """
        解析 Cookie 数据

        Args:
            cookie_data: Cookie JSON 字符串

        Returns:
            解析后的 Cookie 列表，如果格式无效则返回 None
        """
        try:
            data = json.loads(cookie_data)
            # 支持两种格式：
            # 1. 直接数组格式: [{"name": "xxx", "value": "xxx", ...}]
            # 2. 对象格式: {"cookies": [{"name": "xxx", "value": "xxx", ...}]}
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and "cookies" in data:
                return data["cookies"]
            else:
                return None
        except json.JSONDecodeError:
            return None

    async def update_last_used(self, cookie_id: str) -> None:
        """
        更新 Cookie 最后使用时间

        Args:
            cookie_id: Cookie ID
        """
        cookie = await self.get_cookie(cookie_id)
        if cookie:
            cookie.last_used_at = datetime.utcnow()
            self.db.commit()

    async def cleanup_expired_cookies(self) -> int:
        """
        清理过期的 Cookie

        Returns:
            清理的 Cookie 数量
        """
        now = datetime.utcnow()
        expired_cookies = self.db.query(WechatCookie).filter(
            WechatCookie.expires_at < now
        ).all()

        count = len(expired_cookies)
        for cookie in expired_cookies:
            self.db.delete(cookie)

        if count > 0:
            self.db.commit()
            logger.info(f"清理了 {count} 个过期的 Cookie")

        return count


def get_cookie_manager(db: Session = None) -> CookieManager:
    """
    获取 Cookie 管理器实例

    Args:
        db: 数据库会话

    Returns:
        CookieManager 实例
    """
    if db is None:
        db = next(get_db())
    return CookieManager(db)
