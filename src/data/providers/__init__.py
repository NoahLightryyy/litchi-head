"""数据源 Provider 层 —— 抽象数据源接口 + 多实现

分层架构：
    DataCollector（缓存 + 健康监控，横切关注点）
        ↓ 委托
    DataSource（Protocol，数据获取接口）
        ├── AKShareSource    — 当前默认（akshare 爬虫）
        ├── ADataSource      — adata 免费 5 源融合
        ├── ZzshareSource    — zzshare Tushare 兼容零 Token
        └── FallbackSource   — 主源故障自动切换
"""

from src.data.providers.adata_source import ADataSource
from src.data.providers.akshare import AKShareSource
from src.data.providers.base import DataSource
from src.data.providers.fallback import FallbackSource
from src.data.providers.zzshare import ZzshareSource

__all__ = [
    "ADataSource",
    "AKShareSource",
    "DataSource",
    "FallbackSource",
    "ZzshareSource",
]
