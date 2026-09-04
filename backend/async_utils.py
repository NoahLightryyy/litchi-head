"""FastAPI 异步工具 —— 同步调用转异步 + 超时"""

import asyncio
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TypeVar

T = TypeVar("T")

# 后端数据源调用超时（秒）
DATA_TIMEOUT = 15.0


class BoundedSyncRunner:
    """Run blocking calls without allowing timed-out work to grow unbounded.

    Cancelling ``asyncio.to_thread()`` only stops the coroutine waiting for the
    result; Python cannot forcibly stop the already-running thread.  A dedicated
    bounded executor contains that residual work to ``max_workers`` threads and
    lets queued futures be cancelled before they start.
    """

    def __init__(self, *, max_workers: int, thread_name_prefix: str) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=thread_name_prefix,
        )

    async def run[**P, T](
        self,
        func: Callable[P, T],
        *args: P.args,
        **kwargs: P.kwargs,
    ) -> T:
        """Submit one synchronous call to the bounded executor.

        The caller owns the aggregate deadline.  Cancelling this coroutine
        cancels work that has not started, while already-running work remains
        contained by the executor's fixed worker count.
        """
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(
            self._executor,
            partial(func, *args, **kwargs),
        )
        try:
            return await future
        except asyncio.CancelledError:
            future.cancel()
            raise


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
