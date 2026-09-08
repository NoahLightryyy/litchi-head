"""market.py 路由 + 辅助函数测试

覆盖：
1. _calc_heat / _build_top_stocks / _build_chain_map
2. _build_ai_analysis / _calc_rating
3. GET /api/market/indices
4. GET /api/market/sectors
5. GET /api/market/sector/{sector_id}
6. GET /api/market/brief
"""

from __future__ import annotations

import time
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from backend.routers.market import (
    _build_ai_analysis,
    _build_chain_map,
    _build_top_stocks,
    _calc_heat,
    _calc_rating,
)
from src.data.index_quote_runtime import (
    IndexConsensusQuote,
    IndexQuoteCollection,
)
from src.data.providers.eastmoney_boards import (
    BoardQuoteSnapshot,
    BoardSnapshot,
)
from tests.test_backend.conftest import (
    make_board_perf_df,
    make_board_stocks_df,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")
INDEX_AS_OF = datetime(2026, 8, 27, 14, 11, 23, tzinfo=SHANGHAI)


class StubIndexQuoteService:
    def __init__(self, result: IndexQuoteCollection) -> None:
        self.result = result

    def collect(self) -> IndexQuoteCollection:
        return self.result


def make_index_collection(
    *,
    status: str = "success",
    codes: tuple[str, ...] = ("000001", "399001", "399006"),
    missing_codes: list[str] | None = None,
    error_code: str | None = None,
) -> IndexQuoteCollection:
    names = {
        "000001": "上证指数",
        "399001": "深证成指",
        "399006": "创业板指",
    }
    return IndexQuoteCollection(
        status=status,
        quotes=[
            IndexConsensusQuote(
                code=code,
                name=names[code],
                price=3200.0,
                change=10.0,
                change_pct=0.5,
                as_of=INDEX_AS_OF,
                source_count=2,
            )
            for code in codes
        ],
        missing_codes=missing_codes or [],
        error_code=error_code,
    )


# ═══════════════════════════════════════════════════════════════════════
# _calc_heat
# ═══════════════════════════════════════════════════════════════════════


class TestCalcHeat:
    """板块热度计算"""

    def test_high_when_up_ratio_ge_60(self):
        """上涨比例 >= 60% → high"""
        df = pd.DataFrame({"涨跌幅": [1.0, 0.5, 2.0, 3.0, -0.5]})  # 4/5 = 80%
        assert _calc_heat(df) == "high"

    def test_medium_when_up_ratio_40_to_60(self):
        """40% <= 上涨比例 < 60% → medium"""
        df = pd.DataFrame({"涨跌幅": [1.0, 0.5, -0.5, -0.3, -1.0]})  # 2/5 = 40%
        assert _calc_heat(df) == "medium"

    def test_low_when_up_ratio_lt_40(self):
        """上涨比例 < 40% → low"""
        df = pd.DataFrame({"涨跌幅": [1.0, -0.5, -0.3, -1.0]})  # 1/4 = 25%
        assert _calc_heat(df) == "low"

    def test_medium_when_less_than_3_stocks(self):
        """成分股不足 3 只 → medium"""
        df = pd.DataFrame({"涨跌幅": [1.0, -0.5]})
        assert _calc_heat(df) == "medium"

    def test_medium_on_empty_df(self):
        """空 DataFrame → medium"""
        assert _calc_heat(pd.DataFrame()) == "medium"

    def test_custom_change_col(self):
        """支持自定义涨跌幅列名"""
        df = pd.DataFrame({"custom": [1.0, 0.5, 2.0, 3.0, -0.5]})
        assert _calc_heat(df, change_col="custom") == "high"


# ═══════════════════════════════════════════════════════════════════════
# _build_top_stocks
# ═══════════════════════════════════════════════════════════════════════


class TestBuildTopStocks:
    """板块涨幅前 N 股票"""

    def test_normal(self):
        df = make_board_stocks_df()
        result = _build_top_stocks(df, limit=3)
        assert len(result) == 3
        assert result[0] == "平安银行"  # +2.0%

    def test_empty_df(self):
        assert _build_top_stocks(pd.DataFrame()) == []

    def test_missing_sort_col(self):
        """降序列不存在时回退到 '涨跌幅'"""
        df = pd.DataFrame({"名称": ["A"], "涨跌幅": [2.0], "unknown_col": [1.0]})
        result = _build_top_stocks(df, sort_col="missing")
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════
# _build_chain_map
# ═══════════════════════════════════════════════════════════════════════


class TestBuildChainMap:
    """产业链映射必须只来自可核验关系证据。"""

    def test_market_ranking_fields_cannot_create_chain_relationships(self):
        """涨跌幅、价格等行情字段不能被解释成上下游关系。"""
        df = make_board_stocks_df()
        assert _build_chain_map(df, board_type="industry") == []

    def test_empty_df_returns_empty(self):
        assert _build_chain_map(pd.DataFrame(), "industry") == []

    def test_less_than_6_stocks_returns_empty(self):
        """成分股不足 6 只 → 无法分层"""
        df = pd.DataFrame({"名称": [f"S{i}" for i in range(5)], "涨跌幅": [1.0] * 5})
        assert _build_chain_map(df, "industry") == []

    def test_concept_market_fields_also_cannot_create_chain_relationships(self):
        """概念板块同样不能依据行情排名制造产业链节点。"""
        df = make_board_stocks_df()
        assert _build_chain_map(df, "concept") == []


# ═══════════════════════════════════════════════════════════════════════
# _build_ai_analysis
# ═══════════════════════════════════════════════════════════════════════


class TestBuildAiAnalysis:
    """AI 板块分析文本"""

    def test_normal_industry(self):
        df = make_board_stocks_df()
        text = _build_ai_analysis("银行", df, "high", "industry")
        assert "银行" in text
        assert "行业板块" in text
        assert "成分股共" in text
        assert "活跃" in text  # heat=high

    def test_concept_board(self):
        df = make_board_stocks_df()
        text = _build_ai_analysis("AI概念", df, "low", "concept")
        assert "AI概念" in text
        assert "概念板块" in text
        assert "低迷" in text  # heat=low

    def test_empty_stocks(self):
        """无数据时返回提示文本"""
        text = _build_ai_analysis("测试", pd.DataFrame(), "medium", "industry")
        assert "暂无足够数据" in text

    def test_plain_text_formatting(self):
        """行情摘要为可直接呈现的纯文本"""
        df = make_board_stocks_df()
        text = _build_ai_analysis("银行", df, "high", "industry")
        assert "**" not in text  # UI renders plain text, not markdown
        assert "akshare" not in text
        assert "*" not in text


# ═══════════════════════════════════════════════════════════════════════
# _calc_rating
# ═══════════════════════════════════════════════════════════════════════


class TestCalcRating:
    """个股涨跌幅评级"""

    @pytest.mark.parametrize(
        ("change_pct", "expected"),
        [
            (5.0, "A"),
            (4.9, "B+"),
            (2.0, "B+"),
            (1.9, "B"),
            (0.0, "B"),
            (-0.1, "C"),
            (-3.0, "C"),
            (-3.1, "D"),
            (-10.0, "D"),
        ],
    )
    def test_all_ratings(self, change_pct: float, expected: str):
        assert _calc_rating(change_pct) == expected


# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/indices
# ═══════════════════════════════════════════════════════════════════════


class TestGetIndices:
    """三大指数行情"""

    def test_returns_indices(self, client):
        service = StubIndexQuoteService(make_index_collection())
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        codes = {item["code"] for item in data}
        assert codes == {"000001", "399001", "399006"}
        assert resp.json()["meta"]["status"] == "success"
        assert all(item["source_count"] == 2 for item in data)
        assert all(item["as_of"] for item in data)

    def test_meta_fields(self, client):
        service = StubIndexQuoteService(make_index_collection())
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/indices")

        meta = resp.json()["meta"]
        assert "latency_ms" in meta
        assert meta["latency_ms"] >= 0

    def test_missing_all_indices_returns_explicit_empty_without_zero_quotes(
        self,
        client,
    ):
        service = StubIndexQuoteService(make_index_collection(status="empty", codes=()))
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["status"] == "empty"

    def test_missing_some_indices_returns_partial_without_placeholders(
        self,
        client,
    ):
        service = StubIndexQuoteService(
            make_index_collection(
                status="partial",
                codes=("000001",),
                missing_codes=["399001", "399006"],
            )
        )
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        assert [item["code"] for item in resp.json()["data"]] == ["000001"]
        assert resp.json()["meta"]["status"] == "partial"
        assert resp.json()["meta"]["missing_codes"] == ["399001", "399006"]

    def test_indices_failed_collection_returns_stable_contract(self, client):
        service = StubIndexQuoteService(
            make_index_collection(
                status="failed",
                codes=(),
                missing_codes=["000001", "399001", "399006"],
                error_code="MARKET_INDICES_CONFLICTED",
            )
        )
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "MARKET_INDICES_CONFLICTED"
        assert resp.json()["meta"]["status"] == "failed"


# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/sectors
# ═══════════════════════════════════════════════════════════════════════


class TestGetSectors:
    """板块排行"""

    def test_returns_both_industry_and_concept(self, client):
        """同时返回行业板块和概念板块"""
        ind_df = make_board_perf_df()
        con_df = make_board_perf_df(
            rows=[
                {
                    "板块代码": "BK010",
                    "板块名称": "人工智能",
                    "涨跌幅": 2.0,
                    "主力净流入-净额": 1_000_000_000.0,
                },
            ]
        )
        with (
            patch("backend.routers.market._fetch_industry_board_snapshot", return_value=ind_df),
            patch("backend.routers.market._fetch_concept_board_snapshot", return_value=con_df),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3  # 2 industry + 1 concept
        assert resp.json()["meta"]["status"] == "success"

    def test_audited_snapshots_expose_category_time_delay_and_catalog_gap(self, client):
        as_of = datetime(2026, 9, 4, 15, 39, 32, tzinfo=SHANGHAI)
        snapshots = {
            "industry": BoardSnapshot(
                kind="industry",
                fetched_at=as_of,
                cached=False,
                quotes=(
                    BoardQuoteSnapshot(
                        code="BK0001",
                        name="一级行业",
                        change_pct=1.2,
                        fund_flow=300_000_000.0,
                        as_of=as_of,
                    ),
                ),
            ),
            "concept": BoardSnapshot(
                kind="concept",
                fetched_at=as_of,
                cached=True,
                quotes=(
                    BoardQuoteSnapshot(
                        code="BK0002",
                        name="概念板块",
                        change_pct=-0.3,
                        fund_flow=100_000_000.0,
                        as_of=as_of,
                    ),
                ),
            ),
        }
        with patch.object(
            __import__("backend.routers.market", fromlist=["board_snapshots"]).board_snapshots,
            "fetch",
            side_effect=lambda kind: snapshots[kind],
        ):
            resp = client.get("/api/market/sectors?sort=fund_flow")

        assert resp.status_code == 200
        body = resp.json()
        assert body["meta"]["status"] == "partial"
        assert body["meta"]["cached"] is True
        assert body["meta"]["sort_applied"] == "fund_flow"
        assert [item["id"] for item in body["data"]] == ["BK0001", "BK0002"]
        assert body["data"][0] == {
            "id": "BK0001",
            "name": "一级行业",
            "change_pct": 1.2,
            "fund_flow": 3.0,
            "heat": "medium",
            "top_stocks": [],
            "rank": 1,
            "category": "industry",
            "as_of": "2026-09-04T15:39:32+08:00",
            "source": "eastmoney",
            "snapshot_may_be_delayed": True,
        }
        assert {item["code"] for item in body["meta"]["limitations"]} == {
            "BOARD_SNAPSHOT_MAY_BE_DELAYED",
            "BOARD_INDUSTRY_LEVELS_MIXED",
            "BOARD_CATALOG_QUOTE_MISSING",
        }
        assert "2026-09-04T15:39:32+08:00" in body["meta"]["limitations"][0]["message"]

    def test_audited_null_fund_flow_remains_null_and_blocks_fund_sort(self, client):
        as_of = datetime(2026, 9, 4, 15, 39, 32, tzinfo=SHANGHAI)
        snapshots = {
            "industry": BoardSnapshot(
                kind="industry",
                fetched_at=as_of,
                quotes=(
                    BoardQuoteSnapshot(
                        code="BK0001",
                        name="缺资金行业",
                        change_pct=1.2,
                        fund_flow=None,
                        as_of=as_of,
                    ),
                ),
            ),
            "concept": BoardSnapshot(kind="concept", fetched_at=as_of, quotes=()),
        }
        market = __import__("backend.routers.market", fromlist=["board_snapshots"])
        with patch.object(
            market.board_snapshots,
            "fetch",
            side_effect=lambda kind: snapshots[kind],
        ):
            body = client.get("/api/market/sectors?sort=fund_flow").json()

        assert body["data"][0]["fund_flow"] is None
        assert body["meta"]["sort_applied"] == "upstream_order"
        assert "FUND_FLOW_UNAVAILABLE" in {item["code"] for item in body["meta"]["limitations"]}

    def test_empty_boards(self, client):
        """无板块数据时返回空列表"""
        with (
            patch(
                "backend.routers.market._fetch_industry_board_snapshot", return_value=pd.DataFrame()
            ),
            patch(
                "backend.routers.market._fetch_concept_board_snapshot", return_value=pd.DataFrame()
            ),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["status"] == "empty"

    def test_missing_fund_flow_is_null_and_explicitly_limited(self, client):
        current_schema = pd.DataFrame(
            {
                "板块代码": ["BK1556"],
                "板块名称": ["行业板块"],
                "涨跌幅": [8.74],
            }
        )
        with (
            patch(
                "backend.routers.market._fetch_industry_board_snapshot", return_value=current_schema
            ),
            patch(
                "backend.routers.market._fetch_concept_board_snapshot", return_value=pd.DataFrame()
            ),
        ):
            resp = client.get("/api/market/sectors?sort=fund_flow")

        assert resp.status_code == 200
        assert resp.json()["data"][0]["fund_flow"] is None
        assert resp.json()["meta"]["status"] == "partial"
        assert resp.json()["meta"]["sort_requested"] == "fund_flow"
        assert resp.json()["meta"]["sort_applied"] == "upstream_order"
        assert {item["code"] for item in resp.json()["meta"]["limitations"]} == {
            "FUND_FLOW_UNAVAILABLE"
        }

    def test_one_board_source_timeout_returns_partial(self, client):
        con_df = make_board_perf_df()
        with (
            patch(
                "backend.routers.market._fetch_industry_board_snapshot",
                side_effect=TimeoutError("timeout"),
            ),
            patch("backend.routers.market._fetch_concept_board_snapshot", return_value=con_df),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 200
        assert resp.json()["data"]
        assert resp.json()["meta"]["status"] == "partial"
        assert resp.json()["meta"]["failed_sources"] == ["industry"]

    def test_all_board_sources_timeout_returns_failed(self, client):
        with (
            patch(
                "backend.routers.market._fetch_industry_board_snapshot",
                side_effect=TimeoutError("timeout"),
            ),
            patch(
                "backend.routers.market._fetch_concept_board_snapshot",
                side_effect=TimeoutError("timeout"),
            ),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "MARKET_SECTORS_FAILED"
        assert resp.json()["meta"]["status"] == "failed"

    def test_board_sources_share_one_deadline_and_keep_failed_order(self, client):
        """双路阻塞并发等待，不能把两个截止时间串成约 2 倍。"""
        from threading import Event

        release = Event()
        industry_started = Event()
        concept_started = Event()

        def block_industry() -> pd.DataFrame:
            industry_started.set()
            release.wait(timeout=1.0)
            return pd.DataFrame()

        def block_concept() -> pd.DataFrame:
            concept_started.set()
            release.wait(timeout=1.0)
            return pd.DataFrame()

        started_at = time.monotonic()
        try:
            with (
                patch(
                    "backend.routers.market._fetch_industry_board_snapshot",
                    side_effect=block_industry,
                ) as industry_source,
                patch(
                    "backend.routers.market._fetch_concept_board_snapshot",
                    side_effect=block_concept,
                ) as concept_source,
                patch("backend.routers.market.DATA_TIMEOUT", 0.15),
            ):
                resp = client.get("/api/market/sectors")
                first_elapsed = time.monotonic() - started_at
                retry_resp = client.get("/api/market/sectors")
        finally:
            release.set()

        assert industry_started.is_set()
        assert concept_started.is_set()
        assert first_elapsed < 0.28
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "MARKET_SECTORS_FAILED"
        assert resp.json()["meta"]["failed_sources"] == ["industry", "concept"]
        assert retry_resp.status_code == 503
        assert industry_source.call_count == 1
        assert concept_source.call_count == 1

    def test_successful_board_survives_other_source_deadline(self, client):
        """一条来源成功、另一条超时时仍保持既有 partial 失败关闭语义。"""
        from threading import Event

        release = Event()
        concept_started = Event()

        def block_concept() -> pd.DataFrame:
            concept_started.set()
            release.wait(timeout=1.0)
            return pd.DataFrame()

        try:
            with (
                patch(
                    "backend.routers.market._fetch_industry_board_snapshot",
                    return_value=make_board_perf_df(),
                ),
                patch(
                    "backend.routers.market._fetch_concept_board_snapshot",
                    side_effect=block_concept,
                ),
                patch("backend.routers.market.DATA_TIMEOUT", 0.1),
            ):
                resp = client.get("/api/market/sectors")
        finally:
            release.set()

        assert concept_started.is_set()
        assert resp.status_code == 200
        assert resp.json()["data"]
        assert resp.json()["meta"]["status"] == "partial"
        assert resp.json()["meta"]["failed_sources"] == ["concept"]

    def test_sector_has_required_fields(self, client):
        """每个板块包含所有必要字段"""
        df = make_board_perf_df()
        with (
            patch("backend.routers.market._fetch_industry_board_snapshot", return_value=df),
            patch(
                "backend.routers.market._fetch_concept_board_snapshot", return_value=pd.DataFrame()
            ),
        ):
            resp = client.get("/api/market/sectors")

        item = resp.json()["data"][0]
        assert "id" in item
        assert "name" in item
        assert "change_pct" in item
        assert "fund_flow" in item
        assert "rank" in item
        assert "heat" in item

    def test_rank_is_sequential(self, client):
        """排名从 1 开始递增"""
        ind_df = make_board_perf_df()
        with (
            patch("backend.routers.market._fetch_industry_board_snapshot", return_value=ind_df),
            patch(
                "backend.routers.market._fetch_concept_board_snapshot", return_value=pd.DataFrame()
            ),
        ):
            resp = client.get("/api/market/sectors")

        items = resp.json()["data"]
        for i, item in enumerate(items):
            assert item["rank"] == i + 1


# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/sector/{sector_id}
# ═══════════════════════════════════════════════════════════════════════


class TestGetSectorDetail:
    """板块详情"""

    @staticmethod
    def _frames(perf_df: pd.DataFrame, category: str = "industry"):
        empty = pd.DataFrame()
        perf_df = perf_df.copy()
        if "主力净流入-净额" in perf_df.columns:
            perf_df["主力净流入-净额"] /= 100_000_000
        perf_df["数据时间"] = datetime(2026, 9, 4, 15, 39, 32, tzinfo=SHANGHAI)
        perf_df.attrs.update({"audited_snapshot": True, "cached": False})
        return {
            "industry": perf_df if category == "industry" else empty,
            "concept": perf_df if category == "concept" else empty,
        }, {}

    @staticmethod
    def _stocks() -> pd.DataFrame:
        frame = make_board_stocks_df()
        frame["主力净流入"] = [1.5, None, -0.5, 0.25, 0.1, -0.2]
        frame["数据时间"] = datetime(2026, 9, 4, 15, 40, tzinfo=SHANGHAI)
        frame.attrs["cached"] = False
        return frame

    def test_returns_detail_from_audited_snapshot(self, client):
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(make_board_perf_df())),
            patch("backend.routers.market._fetch_board_members_snapshot",
                  return_value=self._stocks()),
        ):
            resp = client.get("/api/market/sector/BK001")
        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]
        assert data["id"] == "BK001" and data["name"] == "银行"
        assert data["chain_map"] == [] and data["fund_flow"] == 5.0
        assert data["stocks"][0]["price"] > 0
        assert data["stocks"][0]["fund_flow"] == 1.5
        assert body["meta"]["status"] == "partial"
        codes = {item["code"] for item in body["meta"]["limitations"]}
        assert {"BOARD_SNAPSHOT_MAY_BE_DELAYED", "CHAIN_MAP_UNAVAILABLE"} <= codes
        assert "FUND_FLOW_UNAVAILABLE" in codes
        assert "2026-09-04T15:39:32+08:00" in body["meta"]["limitations"][0]["message"]

    def test_chain_evidence_is_serialized_with_sources(self, client):
        frame = make_board_perf_df(rows=[{
            "板块代码": "BK1629", "板块名称": "AI应用", "涨跌幅": 2.0,
            "主力净流入-净额": 1_000_000_000.0,
        }])
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(frame, "concept")),
            patch("backend.routers.market._fetch_board_members_snapshot",
                  return_value=self._stocks()),
        ):
            response = client.get("/api/market/sector/BK1629")
        assert response.status_code == 200
        body = response.json()
        graph = body["data"]["chain_evidence"]
        assert len(graph["nodes"]) == 4
        assert graph["sources"][0]["published_on"] == "2024-07-02"
        assert graph["sources"][0]["url"].startswith("https://")
        assert "CHAIN_MAP_UNAVAILABLE" not in {
            item["code"] for item in body["meta"]["limitations"]
        }

    def test_invalid_chain_keeps_quotes_and_reports_limitation(self, client):
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(make_board_perf_df())),
            patch("backend.routers.market._fetch_board_members_snapshot",
                  return_value=self._stocks()),
            patch("backend.routers.market.get_sector_chain", side_effect=ValueError("bad catalog")),
        ):
            response = client.get("/api/market/sector/BK001")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["chain_evidence"] is None
        assert len(body["data"]["stocks"]) == 6
        assert "CHAIN_EVIDENCE_INVALID" in {
            item["code"] for item in body["meta"]["limitations"]
        }

    def test_concept_board_uses_matching_catalog(self, client):
        perf_df = make_board_perf_df(rows=[{
            "板块代码": "BK010", "板块名称": "人工智能", "涨跌幅": 2.0,
            "主力净流入-净额": 1_000_000_000.0,
        }])
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(perf_df, "concept")),
            patch("backend.routers.market._fetch_board_members_snapshot",
                  return_value=self._stocks()) as fetch_members,
        ):
            resp = client.get("/api/market/sector/BK010")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "人工智能"
        fetch_members.assert_called_once_with("BK010", "concept")

    def test_one_catalog_failure_does_not_block_matching_board(self, client):
        perf_df = make_board_perf_df(rows=[{
            "板块代码": "BK010", "板块名称": "人工智能", "涨跌幅": 2.0,
            "主力净流入-净额": 1_000_000_000.0,
        }])
        frames, _ = self._frames(perf_df, "concept")
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=(frames, {"industry": "timeout"})),
            patch("backend.routers.market._fetch_board_members_snapshot",
                  return_value=self._stocks()),
        ):
            resp = client.get("/api/market/sector/BK010")
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "人工智能"

    def test_unknown_board_is_404_without_fabricated_detail(self, client):
        with patch(
            "backend.routers.market._fetch_board_dataframes",
            return_value=({"industry": pd.DataFrame(), "concept": pd.DataFrame()}, {}),
        ):
            resp = client.get("/api/market/sector/BK9999")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "MARKET_SECTOR_NOT_FOUND"
        assert resp.json()["meta"]["status"] == "empty"

    def test_empty_stocks_returns_real_board_basic_info(self, client):
        empty = pd.DataFrame()
        empty.attrs["cached"] = False
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(make_board_perf_df())),
            patch("backend.routers.market._fetch_board_members_snapshot", return_value=empty),
        ):
            body = client.get("/api/market/sector/BK001").json()
        assert body["data"]["stocks"] == []
        assert body["data"]["name"] == "银行"
        assert "暂无足够数据" in body["data"]["ai_analysis"]
        assert "BOARD_MEMBERS_EMPTY" in {
            item["code"] for item in body["meta"]["limitations"]
        }

    def test_missing_price_is_omitted_instead_of_becoming_zero(self, client):
        stocks = self._stocks()
        stocks.loc[0, "现价"] = None
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(make_board_perf_df())),
            patch("backend.routers.market._fetch_board_members_snapshot", return_value=stocks),
        ):
            body = client.get("/api/market/sector/BK001").json()
        assert len(body["data"]["stocks"]) == len(stocks) - 1
        assert all(stock["price"] != 0 for stock in body["data"]["stocks"])
        assert "MEMBER_QUOTE_UNAVAILABLE" in {
            item["code"] for item in body["meta"]["limitations"]
        }

    @pytest.mark.parametrize("timed_out", [False, True])
    def test_members_failure_returns_structured_retryable_503(self, client, timed_out):
        error = TimeoutError("timeout") if timed_out else RuntimeError("upstream failed")
        with (
            patch("backend.routers.market._fetch_board_dataframes",
                  return_value=self._frames(make_board_perf_df())),
            patch("backend.routers.market._fetch_board_members_snapshot", side_effect=error),
        ):
            resp = client.get("/api/market/sector/BK001")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == (
            "MARKET_SECTOR_DETAIL_TIMEOUT" if timed_out else "MARKET_SECTOR_DETAIL_FAILED"
        )
        assert resp.json()["meta"]["failed_sources"] == ["industry"]

    def test_catalog_failure_prevents_false_not_found(self, client):
        with patch(
            "backend.routers.market._fetch_board_dataframes",
            return_value=(
                {"industry": pd.DataFrame(), "concept": pd.DataFrame()},
                {"industry": "timeout"},
            ),
        ):
            resp = client.get("/api/market/sector/BK001")
        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "MARKET_SECTOR_DETAIL_TIMEOUT"
        assert resp.json()["meta"]["failed_sources"] == ["industry"]

# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/brief
# ═══════════════════════════════════════════════════════════════════════


class TestGetMacroBrief:
    """AI 宏观简报"""

    def test_returns_brief(self, client):
        service = StubIndexQuoteService(make_index_collection())
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/brief")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "summary" in data
        assert "generated_at" in data
        assert "上证指数" in data["summary"]

    def test_empty_quotes_returns_empty_without_success_object(self, client):
        """无指数行情时显式 empty，不返回看似成功的“暂无数据”简报。"""
        service = StubIndexQuoteService(make_index_collection(status="empty", codes=()))
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/brief")

        assert resp.status_code == 200
        assert resp.json()["data"] is None
        assert resp.json()["meta"]["status"] == "empty"

    def test_meta_timing(self, client):
        service = StubIndexQuoteService(make_index_collection())
        with patch("backend.routers.market.index_quote_service", service):
            resp = client.get("/api/market/brief")

        meta = resp.json()["meta"]
        assert "latency_ms" in meta
        assert meta["latency_ms"] >= 0


# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/hot-news
# ═══════════════════════════════════════════════════════════════════════


class TestHotNews:
    """热点快讯"""

    def test_caixin_publication_time_reaches_http(self, client):
        import httpx

        response = httpx.Response(
            200, request=httpx.Request("GET", "https://cxdata.caixin.com"),
            json={"data": {"data": [{"summary": "原摘要", "time": 1788569539}]}},
        )
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("src.data.providers.caixin_news.httpx.get", return_value=response),
        ):
            body = client.get("/api/market/hot-news").json()
        assert body["data"][0]["date"] == "2026-09-05T08:52:19+08:00"
        assert body["meta"]["status"] == "success"
        assert body["meta"]["limitations"] == []

    def test_returns_hot_news(self, client):
        """正常返回热点新闻列表"""
        mock_df = pd.DataFrame(
            {
                "title": ["新闻1", "新闻2"],
                "date": ["2024-01-02", "2024-01-02"],
                "source": ["源1", "源2"],
                "url": ["http://url1", "http://url2"],
            }
        )
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("backend.routers.market.fetch_caixin_news", return_value=mock_df),
        ):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 2
        assert data[0]["title"] == "新闻1"
        assert resp.json()["meta"]["status"] == "success"

    def test_current_caixin_schema_is_partial_not_empty_success(self, client):
        """2026-08-26 实测字段 tag/summary/url 可恢复标题，但发布时间不可伪造。"""
        mock_df = pd.DataFrame(
            {
                "tag": ["市场动态"],
                "summary": ["联储官员发表最新讲话"],
                "url": ["https://database.caixin.com/2026-08-26/example.html"],
            }
        )
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("backend.routers.market.fetch_caixin_news", return_value=mock_df),
        ):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 200
        assert resp.json()["meta"]["status"] == "partial"
        assert resp.json()["data"] == [
            {
                "title": "联储官员发表最新讲话",
                "date": None,
                "source": "财新数据通",
                "url": "https://database.caixin.com/2026-08-26/example.html",
            }
        ]
        assert resp.json()["meta"]["limitations"][0]["code"] == "PUBLISHED_AT_MISSING"

    def test_hot_news_fields(self, client):
        """每条新闻含必要字段"""
        mock_df = pd.DataFrame(
            {
                "title": ["测试新闻"],
                "date": ["2024-01-02"],
                "source": ["测试源"],
                "url": ["http://example.com"],
            }
        )
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("backend.routers.market.fetch_caixin_news", return_value=mock_df),
        ):
            resp = client.get("/api/market/hot-news")

        item = resp.json()["data"][0]
        assert "title" in item
        assert "date" in item
        assert "source" in item
        assert "url" in item

    def test_empty_data(self, client):
        """空 DataFrame 返回空列表"""
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("backend.routers.market.fetch_caixin_news", return_value=pd.DataFrame()),
        ):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 200
        assert resp.json()["data"] == []
        assert resp.json()["meta"]["status"] == "empty"

    def test_error_fallback_to_stale_cache(self, client):
        """API 异常时返回过期缓存（如果有）

        原理：直接往 _HOT_NEWS_CACHE 写入旧时间戳的数据，
        绕过正常请求路径（避免新鲜缓存提前返回），
        然后让 API 抛异常触发 stale 返回路径。
        """
        import time

        from backend.routers.market import _HOT_NEWS_CACHE

        _HOT_NEWS_CACHE.clear()
        _HOT_NEWS_CACHE["data"] = [
            {"title": "过期新闻", "date": "2024-01-01", "source": "测试", "url": ""},
        ]
        _HOT_NEWS_CACHE["ts"] = time.time() - 300  # 5 分钟前->过期

        with patch("backend.routers.market.fetch_caixin_news", side_effect=RuntimeError("API异常")):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 1
        assert data[0]["title"] == "过期新闻"
        assert resp.json()["meta"]["status"] == "stale"

    def test_error_no_cache_returns_failed(self, client):
        """API 异常且无缓存时不得伪装成成功空列表。"""
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch("backend.routers.market.fetch_caixin_news", side_effect=RuntimeError("API异常")),
        ):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "HOT_NEWS_FAILED"
        assert resp.json()["meta"]["status"] == "failed"

    def test_nonempty_unknown_schema_returns_failed(self, client):
        with (
            patch("backend.routers.market._HOT_NEWS_CACHE", {}),
            patch(
                "backend.routers.market.fetch_caixin_news",
                return_value=pd.DataFrame({"unknown": ["value"]}),
            ),
        ):
            resp = client.get("/api/market/hot-news")

        assert resp.status_code == 503
        assert resp.json()["error"]["code"] == "HOT_NEWS_SCHEMA_INVALID"


def test_homepage_market_openapi_freezes_status_and_failed_response(client):
    schema = client.get("/openapi.json").json()
    components = schema["components"]["schemas"]
    statuses = schema["components"]["schemas"]["MarketMeta"]["properties"]["status"]["enum"]
    assert statuses == ["success", "partial", "empty", "stale", "failed"]
    assert {
        "source_diagnostics",
        "sort_requested",
        "sort_applied",
    } <= components["MarketMeta"]["properties"].keys()
    assert {
        "as_of",
        "source_count",
        "cached",
    } <= components["IndexQuoteResp"]["properties"].keys()
    sector = components["SectorItemResp"]
    assert "anyOf" in sector["properties"]["fund_flow"]
    assert sector["properties"]["fund_flow"]["description"] == "主力净流入，单位亿元"
    assert sector["properties"]["category"]["enum"] == ["industry", "concept"]
    assert "anyOf" in sector["properties"]["as_of"]
    assert sector["properties"]["source"]["const"] == "eastmoney"
    assert sector["properties"]["snapshot_may_be_delayed"]["type"] == "boolean"

    for path in (
        "/api/market/indices",
        "/api/market/sectors",
        "/api/market/brief",
        "/api/market/hot-news",
    ):
        responses = schema["paths"][path]["get"]["responses"]
        assert "200" in responses
        assert "503" in responses

    detail_responses = schema["paths"]["/api/market/sector/{sector_id}"]["get"]["responses"]
    assert "404" in detail_responses
    assert "503" in detail_responses
    assert components["SectorDetailResp"]["properties"]["fund_flow"]["description"] == (
        "主力净流入，单位亿元"
    )
    assert components["SectorStockResp"]["properties"]["fund_flow"]["description"] == (
        "主力净流入，单位亿元"
    )
    detail_error = components["SectorDetailErrorBody"]["properties"]
    assert detail_error["code"]["enum"] == [
        "MARKET_SECTOR_DETAIL_TIMEOUT",
        "MARKET_SECTOR_DETAIL_FAILED",
    ]
    assert detail_error["retryable"]["const"] is True
    assert detail_error["retry_mode"]["const"] == "client_controlled"
