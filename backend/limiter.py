"""API 速率限制器

集中管理 Limiter 实例，供 main.py + 各路由模块使用。

用法：
    from backend.limiter import limiter

    @router.post("/endpoint")
    @limiter.limit("6/minute")
    async def handler(request: Request, ...):
        ...
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.config import RATE_LIMIT_ENABLED

limiter = Limiter(
    key_func=get_remote_address,
    enabled=RATE_LIMIT_ENABLED,
)
"""全局 Limiter 实例。enabled 由 LITCHI_RATE_LIMIT_ENABLED 环境变量控制。"""
