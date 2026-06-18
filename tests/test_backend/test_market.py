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

from unittest.mock import patch

import pandas as pd
import pytest

from backend.routers.market import (
    ChainNodeResp,
    ChainStageResp,
    _build_ai_analysis,
    _build_chain_map,
    _build_top_stocks,
    _calc_heat,
    _calc_rating,
)
from tests.test_backend.conftest import (
    make_board_perf_df,
    make_board_stocks_df,
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
    """产业链映射"""

    def test_normal_industry(self):
        """行业板块 → 3 层结构"""
        df = make_board_stocks_df()
        result = _build_chain_map(df, board_type="industry")
        assert len(result) == 3
        assert result[0].stage == "领涨龙头"
        assert result[1].stage == "中坚力量"
        assert result[2].stage == "基础层"

    def test_empty_df_returns_empty(self):
        assert _build_chain_map(pd.DataFrame(), "industry") == []

    def test_less_than_6_stocks_returns_empty(self):
        """成分股不足 6 只 → 无法分层"""
        df = pd.DataFrame(
            {"名称": [f"S{i}" for i in range(5)], "涨跌幅": [1.0] * 5}
        )
        assert _build_chain_map(df, "industry") == []

    def test_chain_node_types(self):
        """每层节点格式正确"""
        df = make_board_stocks_df()
        result = _build_chain_map(df, "concept")
        for stage in result:
            assert isinstance(stage, ChainStageResp)
            assert stage.stage
            for node in stage.nodes:
                assert isinstance(node, ChainNodeResp)
                assert node.companies


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

    def test_html_formatting(self):
        """分析文本包含 Markdown 格式"""
        df = make_board_stocks_df()
        text = _build_ai_analysis("银行", df, "high", "industry")
        assert "**" in text  # markdown bold
        assert "*" in text  # markdown italic


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

    def test_returns_indices(self, client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        codes = {item["code"] for item in data}
        assert codes == {"000001", "399001", "399006"}

    def test_meta_fields(self, client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")

        meta = resp.json()["meta"]
        assert "latency_ms" in meta
        assert meta["latency_ms"] >= 0

    def test_missing_index_fills_default(self, client, mock_collector):
        """缺失的指数用空值填充"""
        mock_collector._quotes = []  # 空行情列表
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/indices")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3
        # 所有指数 price=0.0
        assert all(item["price"] == 0.0 for item in data)


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
                    "板块代码": "BK010", "板块名称": "人工智能",
                    "涨跌幅": 2.0, "主力净流入-净额": 1_000_000_000.0,
                },
            ]
        )
        with (
            patch("akshare.stock_board_industry_name_em", return_value=ind_df),
            patch("akshare.stock_board_concept_name_em", return_value=con_df),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) == 3  # 2 industry + 1 concept

    def test_empty_boards(self, client):
        """无板块数据时返回空列表"""
        with (
            patch("akshare.stock_board_industry_name_em", return_value=pd.DataFrame()),
            patch("akshare.stock_board_concept_name_em", return_value=pd.DataFrame()),
        ):
            resp = client.get("/api/market/sectors")

        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_sector_has_required_fields(self, client):
        """每个板块包含所有必要字段"""
        df = make_board_perf_df()
        with (
            patch("akshare.stock_board_industry_name_em", return_value=df),
            patch("akshare.stock_board_concept_name_em", return_value=pd.DataFrame()),
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
            patch("akshare.stock_board_industry_name_em", return_value=ind_df),
            patch("akshare.stock_board_concept_name_em", return_value=pd.DataFrame()),
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

    def test_returns_detail(self, client, mock_collector):
        stocks_df = make_board_stocks_df()
        perf_df = make_board_perf_df()
        with (
            patch("backend.routers.market.collector", mock_collector),
            patch("akshare.stock_board_industry_cons_em", return_value=stocks_df),
            patch("akshare.stock_board_industry_name_em", return_value=perf_df),
        ):
            resp = client.get("/api/market/sector/BK001")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["id"] == "BK001"
        assert data["name"] == "银行"
        assert "stocks" in data
        assert "chain_map" in data
        assert "ai_analysis" in data
        assert "heat" in data

    def test_concept_board(self, client, mock_collector):
        """概念板块也能正常获取"""
        stocks_df = make_board_stocks_df()
        perf_df = make_board_perf_df(
            rows=[{
                "板块代码": "BK010", "板块名称": "人工智能",
                "涨跌幅": 2.0, "主力净流入-净额": 1_000_000_000.0,
            }]
        )
        with (
            patch("backend.routers.market.collector", mock_collector),
            patch("akshare.stock_board_concept_cons_em", return_value=stocks_df),
            patch("akshare.stock_board_concept_name_em", return_value=perf_df),
        ):
            resp = client.get("/api/market/sector/BK010")

        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "人工智能"

    def test_empty_stocks_returns_basic_info(self, client, mock_collector):
        """成分股为空时仍返回板块基本信息"""
        perf_df = make_board_perf_df()
        with (
            patch("backend.routers.market.collector", mock_collector),
            patch("akshare.stock_board_industry_cons_em", return_value=pd.DataFrame()),
            patch("akshare.stock_board_industry_name_em", return_value=perf_df),
        ):
            resp = client.get("/api/market/sector/BK001")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["stocks"] == []
        assert data["chain_map"] == []
        assert "暂无足够数据" in data["ai_analysis"]

    def test_ai_rating_in_stocks(self, client, mock_collector):
        """成分股含 ai_rating 字段"""
        stocks_df = make_board_stocks_df()
        perf_df = make_board_perf_df()
        with (
            patch("backend.routers.market.collector", mock_collector),
            patch("akshare.stock_board_industry_cons_em", return_value=stocks_df),
            patch("akshare.stock_board_industry_name_em", return_value=perf_df),
        ):
            resp = client.get("/api/market/sector/BK001")

        stocks = resp.json()["data"]["stocks"]
        assert all("ai_rating" in s for s in stocks)
        assert any(s["ai_rating"] != "B" for s in stocks)  # 有涨跌幅差异


# ═══════════════════════════════════════════════════════════════════════
# GET /api/market/brief
# ═══════════════════════════════════════════════════════════════════════


class TestGetMacroBrief:
    """AI 宏观简报"""

    def test_returns_brief(self, client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/brief")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "summary" in data
        assert "generated_at" in data
        assert "上证指数" in data["summary"]

    def test_empty_quotes(self, client, mock_collector):
        """无行情数据时显示'暂无数据'"""
        mock_collector._quotes = []
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/brief")

        assert resp.status_code == 200
        assert resp.json()["data"]["summary"] == "暂无数据"

    def test_meta_timing(self, client, mock_collector):
        with patch("backend.routers.market.collector", mock_collector):
            resp = client.get("/api/market/brief")

        meta = resp.json()["meta"]
        assert "latency_ms" in meta
        assert meta["latency_ms"] >= 0
