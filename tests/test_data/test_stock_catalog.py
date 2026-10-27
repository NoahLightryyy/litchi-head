from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import MagicMock

import pandas as pd
import pytest

from src.data.collector import DataCollector, HealthStats
from src.data.models import StockInfo
from src.data.providers.stock_catalog import (
    ExchangeStockCatalog,
    PartialStockCatalogError,
    StockCatalogSnapshot,
    _exchange_loaders,
)


def test_one_failed_exchange_keeps_other_markets_and_retries(mocker):
    clock = mocker.patch("src.data.providers.stock_catalog.time.monotonic", return_value=100.0)
    sh = MagicMock(
        side_effect=[ConnectionError("reset"), [StockInfo(code="600001", name="沪市公司")]]
    )
    sz = MagicMock(return_value=[StockInfo(code="002885", name="京泉华")])
    catalog = ExchangeStockCatalog({"沪市": sh, "深市": sz})
    first = catalog.snapshot()
    assert first.failed_markets == ["沪市"]
    assert first.items[0].name == "京泉华"
    assert not first.complete
    assert catalog.snapshot() == first
    assert sh.call_count == sz.call_count == 1
    clock.return_value = 116.0
    assert catalog.snapshot().complete
    assert sh.call_count == 2
    assert sz.call_count == 1  # Successful exchange data does not need another request.


def test_slow_exchange_is_bounded_and_never_duplicated():
    started, release = Event(), Event()

    def slow():
        started.set()
        assert release.wait(timeout=3)
        return [StockInfo(code="600001", name="沪市公司")]

    sh = MagicMock(side_effect=slow)
    sz = MagicMock(return_value=[StockInfo(code="002885", name="京泉华")])
    catalog = ExchangeStockCatalog({"沪市": sh, "深市": sz})
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(catalog.snapshot, timeout=0.05) for _ in range(4)]
            assert started.wait(timeout=1)
            for future in futures:
                result = future.result(timeout=1)
                assert result.items[0].code == "002885"
                assert result.failed_markets == ["沪市"]
        assert sh.call_count == sz.call_count == 1
    finally:
        release.set()
    assert catalog.snapshot().complete


def test_collectors_keep_partial_data_out_of_complete_cache(mocker):
    clock = mocker.patch("src.data.cache.time.time", return_value=100.0)
    stats = HealthStats()
    mocker.patch("src.data.collector._health_stats", stats)
    partial = StockCatalogSnapshot(
        items=[StockInfo(code="002885", name="京泉华")], failed_markets=["沪市"]
    )
    source = MagicMock()
    source.get_all_stocks.side_effect = [PartialStockCatalogError(partial), partial.items]
    collector = DataCollector(source=source)
    assert collector.get_stock_catalog() == partial
    assert collector.get_all_stocks() == partial.items
    assert source.get_all_stocks.call_count == 1
    assert collector.cache.get("all_stocks") is None
    assert stats.snapshot()["all_stocks"]["last_error_code"] == "STOCK_CATALOG_PARTIAL"
    clock.return_value = 116.0
    assert collector.get_stock_catalog().complete
    assert stats.snapshot()["all_stocks"]["current_status"] == "healthy"


def test_exchange_loaders_reuse_all_four_existing_directories(mocker):
    sh = mocker.patch(
        "akshare.stock_info_sh_name_code",
        return_value=pd.DataFrame(
            [
                {"证券代码": "600001", "证券简称": "沪市公司"},
            ]
        ),
    )
    mocker.patch(
        "akshare.stock_info_sz_name_code",
        return_value=pd.DataFrame(
            [
                {"A股代码": "002885", "A股简称": "京泉华"},
            ]
        ),
    )
    mocker.patch(
        "akshare.stock_info_bj_name_code",
        return_value=pd.DataFrame(
            [
                {"证券代码": "920001", "证券简称": "北交公司"},
            ]
        ),
    )
    loaders = _exchange_loaders()
    assert loaders["深市"]()[0] == StockInfo(code="002885", name="京泉华", market="sz")
    assert loaders["北交所"]()[0].market == "bj"
    loaders["沪市主板"]()
    loaders["科创板"]()
    assert [call.kwargs["symbol"] for call in sh.call_args_list] == ["主板A股", "科创板"]


@pytest.mark.parametrize(
    "frame",
    [pd.DataFrame()]
    + [pd.DataFrame([{"A股代码": code, "A股简称": "京泉华"}])
       for code in ("bad", "", "0", "000000")],
)
def test_invalid_or_empty_identity_is_not_success(mocker, frame):
    mocker.patch("akshare.stock_info_sz_name_code", return_value=frame)
    with pytest.raises(ValueError):
        _exchange_loaders()["深市"]()
