"""backend 工具模块测试 — config.py + async_utils.py

覆盖：
1. config.py — 环境变量解析、数据源选择
2. async_utils.py — run_sync 超时行为
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import patch

import pytest

# ═══════════════════════════════════════════════════════════════════════
# config.py
# ═══════════════════════════════════════════════════════════════════════


class TestConfigRateLimits:
    """速率限制配置"""

    def test_default_values(self):
        """默认限流值"""
        # 清理环境变量以确保使用默认值
        with patch.dict(os.environ, {}, clear=True):
            # 重新导入模块以触发配置刷新
            import importlib

            import backend.config as cfg

            importlib.reload(cfg)

            assert cfg.RATE_LIMIT_ENABLED is True
            assert cfg.RATE_LIMIT_DEBATE_RUN == "6/minute"
            assert cfg.RATE_LIMIT_DEBATE_STATUS == "30/minute"
            assert cfg.RATE_LIMIT_DEBATE_RESULT == "30/minute"

    def test_disabled_via_env(self):
        """LITCHI_RATE_LIMIT_ENABLED=0 时关闭限流"""
        with patch.dict(os.environ, {"LITCHI_RATE_LIMIT_ENABLED": "0"}, clear=True):
            import importlib

            import backend.config as cfg

            importlib.reload(cfg)

            assert cfg.RATE_LIMIT_ENABLED is False

    def test_custom_limits_via_env(self):
        """环境变量可覆盖限流值"""
        with patch.dict(
            os.environ,
            {
                "LITCHI_RATE_LIMIT_DEBATE_RUN": "3/minute",
                "LITCHI_RATE_LIMIT_DEBATE_STATUS": "60/minute",
            },
            clear=True,
        ):
            import importlib

            import backend.config as cfg

            importlib.reload(cfg)

            assert cfg.RATE_LIMIT_DEBATE_RUN == "3/minute"
            assert cfg.RATE_LIMIT_DEBATE_STATUS == "60/minute"


class TestConfigDataSource:
    """数据源选择配置"""

    def test_akshare_forced(self):
        """LITCHI_DATASOURCE=akshare"""
        with patch.dict(os.environ, {"LITCHI_DATASOURCE": "akshare"}, clear=True):
            import importlib

            import backend.config as cfg

            importlib.reload(cfg)

            result = cfg.setup_production_source()
            assert "akshare (forced by LITCHI_DATASOURCE=akshare)" in result


# ═══════════════════════════════════════════════════════════════════════
# async_utils.py
# ═══════════════════════════════════════════════════════════════════════


class TestRunSync:
    """run_sync — 同步转异步"""

    async def test_sync_function(self):
        """同步函数通过 run_sync 可正常调用"""
        from backend.async_utils import run_sync

        result = await run_sync(lambda: 42)
        assert result == 42

    async def test_with_args(self):
        """带参数的同步函数"""
        from backend.async_utils import run_sync

        def add(a: int, b: int) -> int:
            return a + b

        result = await run_sync(add, 1, 2)
        assert result == 3

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        """超时超过 DATA_TIMEOUT 抛 TimeoutError"""
        from backend.async_utils import DATA_TIMEOUT, run_sync

        def slow() -> None:
            import time
            time.sleep(DATA_TIMEOUT + 1)

        with pytest.raises(asyncio.TimeoutError):
            await run_sync(slow)
