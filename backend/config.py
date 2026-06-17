"""生产环境数据源配置

使用方式：在应用入口（main.py）中 import 本模块即可自动配置。
可通过环境变量快速切换。

支持的数据源（按优先级）：
1. ADataSource — adata 5 源融合自动切换（同花顺/东财/新浪/腾讯/百度），免费
2. AKShareSource — akshare 原生数据源，作为 fallback
3. ZzshareSource — Tushare 兼容零 Token 零积分数据源（备用）

环境变量：
  LITCHI_DATASOURCE=auto      自动选择（默认，先用 adata，失败降级 akshare）
  LITCHI_DATASOURCE=akshare   强制使用 akshare
  LITCHI_DATASOURCE=adata     强制使用 adata（不降级）
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger("backend.config")


def setup_production_source() -> str:
    """配置生产数据源

    Returns:
        使用的数据源名称
    """
    mode = os.environ.get("LITCHI_DATASOURCE", "auto")

    if mode == "akshare":
        # 强制 akshare
        return "akshare (forced by LITCHI_DATASOURCE=akshare)"

    if mode == "adata":
        # 强制 adata
        return _try_set_adata_primary()

    # auto: 尝试 adata，失败用 akshare
    return _try_set_adata_fallback()


def _try_set_adata_primary() -> str:
    """尝试设置 ADataSource 为主数据源"""
    from src.data.collector import DataCollector  # noqa: PLC0415
    from src.data.providers import ADataSource  # noqa: PLC0415

    try:
        _check_adata_installed()
    except ImportError:
        logger.warning("adata 未安装，无法使用 ADataSource")
        return "akshare (adata not installed)"

    DataCollector.default_source = ADataSource()
    logger.info("✅ 生产数据源: ADataSource")
    return "adata"


def _try_set_adata_fallback() -> str:
    """尝试设置 FallbackSource(ADataSource, AKShareSource)"""
    from src.data.collector import DataCollector  # noqa: PLC0415
    from src.data.providers import ADataSource, AKShareSource, FallbackSource  # noqa: PLC0415

    try:
        _check_adata_installed()
    except ImportError:
        logger.warning("adata 未安装，使用 AKShareSource 作为主数据源")
        return "akshare (adata not installed)"

    source = FallbackSource(
        primary=ADataSource(),
        fallback=AKShareSource(),
        max_failures=3,
    )
    DataCollector.default_source = source
    logger.info("✅ 生产数据源: FallbackSource(ADataSource → AKShareSource)")
    return "fallback(adata→akshare)"


def _check_adata_installed() -> None:
    """检查 adata 是否可用，不可用则抛 ImportError"""
    try:
        import adata  # noqa: PLC0415, F401
    except ImportError:
        raise ImportError("adata package not installed")
