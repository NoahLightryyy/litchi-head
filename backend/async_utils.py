"""FastAPI 异步工具 —— 同步调用转异步 + 超时"""

import asyncio
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")

# 后端数据源调用超时（秒）
DATA_TIMEOUT = 15.0


async def run_sync[**P, T](
    func: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """在线程池中执行同步函数，带超时，不阻塞事件循环

    Args:
        func: 同步函数
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        函数返回值

    Raises:
        asyncio.TimeoutError: 超过 DATA_TIMEOUT 秒未完成
    """
    return await asyncio.wait_for(
        asyncio.to_thread(func, *args, **kwargs),
        timeout=DATA_TIMEOUT,
    )
