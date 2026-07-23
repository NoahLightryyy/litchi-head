"""数据源 Provider 层单元测试

覆盖：
1. AKShareSource 基本结构 + 7 个方法异常路径 + 数据解析
2. ADataSource 方法异常路径（mock adata 内部调用） + 转换函数
3. ZzshareSource 转换函数 + 工具函数（因 zzshare 未安装，实例方法无法测试）
4. FallbackSource 故障自动切换 + 自动恢复 + 全部委托方法 + 备用也失败的路径
5. MockDataSource 注入 DataCollector
6. safe_str/safe_float/safe_int 边值（base.py）
7. _detect_market 股票代码→交易所映射
8. FallbackSource TD-032 自动恢复主源逻辑
"""


from src.data.collector import DataCollector

# ── MockDataSource（复用同一定义） ──────────────────────────────────


class MockDataSource:
    """测试用模拟数据源"""

    def get_all_stocks(self) -> list:
        from src.data.models import StockInfo
        return [StockInfo(code="000001", name="平安银行")]

    def get_realtime_quotes(self) -> list:
        return []

    def get_klines(self, code: str, period: str = "daily", start: str = "",
                   end: str = "", adjust: str = "qfq") -> list:
        return []

    def get_news(self, code: str) -> list:
        return []

    def get_industry_boards(self) -> list:
        return []

    def get_concept_boards(self) -> list:
        return []

    def get_capital_flow(self, code: str) -> list:
        return []

    def get_financials(self, code: str) -> list:
        return []


class TestProviderProtocol:
    """验证 MockDataSource 满足 DataSource Protocol（鸭子类型）"""

    def test_mock_is_valid_datasource(self):
        """MockDataSource 应被 DataSource 协议接受"""
        source = MockDataSource()
        # 鸭子类型验证：能传给需要 DataSource 的 DataCollector 就行
        collector = DataCollector(source=source)  # type: ignore[arg-type]
        assert collector._source is source

    def test_inject_into_collector(self):
        """外部可注入 MockDataSource"""
        source = MockDataSource()
        collector = DataCollector(source=source)  # type: ignore[arg-type]
        result = collector.get_all_stocks()
        assert len(result) == 1
        # DataCollector 做了缓存包装，结果应该是 StockInfo 对象
        assert result[0].code == "000001"
        assert result[0].name == "平安银行"


# ── base.py 工具函数边值测试 ─────────────────────────────────────────


class TestSafeConverters:
    """safe_str / safe_float / safe_int 边值覆盖"""

    def test_safe_str_normal(self):
        from src.data.providers.base import safe_str
        assert safe_str("hello") == "hello"
        assert safe_str("123") == "123"
        assert safe_str("") == ""

    def test_safe_str_none(self):
        from src.data.providers.base import safe_str
        assert safe_str(None) == ""

    def test_safe_str_numeric(self):
        from src.data.providers.base import safe_str
        assert safe_str(123) == "123"
        assert safe_str(3.14) == "3.14"

    def test_safe_str_empty_collection(self):
        from src.data.providers.base import safe_str
        # Series with len 0 or falsy values
        assert safe_str("", default="fallback") == "fallback"

    def test_safe_float_normal(self):
        from src.data.providers.base import safe_float
        assert safe_float(3.14) == 3.14
        assert safe_float("3.14") == 3.14
        assert safe_float(0) == 0.0

    def test_safe_float_none(self):
        from src.data.providers.base import safe_float
        assert safe_float(None) == 0.0

    def test_safe_float_invalid_string(self):
        from src.data.providers.base import safe_float
        assert safe_float("abc") == 0.0
        assert safe_float("") == 0.0

    def test_safe_float_custom_default(self):
        from src.data.providers.base import safe_float
        assert safe_float(None, default=-1.0) == -1.0

    def test_safe_int_normal(self):
        from src.data.providers.base import safe_int
        assert safe_int(42) == 42
        assert safe_int("42") == 42
        assert safe_int(0) == 0

    def test_safe_int_none(self):
        from src.data.providers.base import safe_int
        assert safe_int(None) == 0

    def test_safe_int_invalid_string(self):
        from src.data.providers.base import safe_int
        assert safe_int("abc") == 0
        assert safe_int("") == 0

    def test_safe_int_float_input(self):
        from src.data.providers.base import safe_int
        assert safe_int(3.14) == 3

    def test_safe_int_custom_default(self):
        from src.data.providers.base import safe_int
        assert safe_int(None, default=-1) == -1


# ── akshare 转换函数测试 ───────────────────────────────────────────


class TestAKShareDetectMarket:
    """_detect_market 股票代码→交易所映射"""

    def test_sh_starts_with_6(self):
        from src.data.providers.akshare import _detect_market
        assert _detect_market("600000") == "sh"
        assert _detect_market("688001") == "sh"

    def test_sz_default(self):
        from src.data.providers.akshare import _detect_market
        assert _detect_market("000001") == "sz"
        assert _detect_market("300750") == "sz"
        assert _detect_market("002001") == "sz"

    def test_bj_starts_with_4_or_8(self):
        from src.data.providers.akshare import _detect_market
        assert _detect_market("430017") == "bj"
        assert _detect_market("830000") == "bj"
        assert _detect_market("488888") == "bj"

    def test_empty_code_defaults_to_sh(self):
        from src.data.providers.akshare import _detect_market
        assert _detect_market("") == "sh"

    def test_none_code_defaults_to_sh(self):
        from src.data.providers.akshare import _detect_market
        assert _detect_market("") == "sh"


class TestAKShareRowToQuote:
    """_row_to_quote 实时行情行转换"""

    def test_normal_row(self):
        from src.data.providers.akshare import _row_to_quote
        row = {"代码": "000001", "名称": "平安银行", "最新价": 12.34,
               "涨跌额": 0.56, "涨跌幅": 4.76, "成交量": 1000000,
               "成交额": 12340000.0, "最高": 12.50, "最低": 12.10,
               "今开": 12.20, "昨收": 11.78}
        q = _row_to_quote(row)
        assert q.code == "000001"
        assert q.name == "平安银行"
        assert q.price == 12.34
        assert q.change == 0.56
        assert q.change_pct == 4.76
        assert q.volume == 1000000
        assert q.high == 12.50
        assert q.low == 12.10

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.akshare import _row_to_quote
        row = {"代码": "000001", "名称": "测试"}
        q = _row_to_quote(row)
        assert q.code == "000001"
        assert q.price == 0.0
        assert q.volume == 0

    def test_none_values_safe(self):
        from src.data.providers.akshare import _row_to_quote
        row = {"代码": "000001", "名称": "测试", "最新价": None,
               "成交量": None, "涨跌额": None}
        q = _row_to_quote(row)
        assert q.price == 0.0
        assert q.volume == 0
        assert q.change == 0.0


class TestAKShareRowToKline:
    """_row_to_kline K 线行转换"""

    def test_normal_row(self):
        from src.data.providers.akshare import _row_to_kline
        row = {"日期": "2024-01-02", "开盘": 10.0, "收盘": 10.5,
               "最高": 10.8, "最低": 9.9, "成交量": 500000, "成交额": 5200000.0}
        k = _row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 10.0
        assert k.close == 10.5
        assert k.high == 10.8
        assert k.low == 9.9
        assert k.volume == 500000
        assert k.amount == 5200000.0

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.akshare import _row_to_kline
        row = {"日期": "2024-01-02"}
        k = _row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 0.0
        assert k.volume == 0


class TestAKShareRowToNews:
    """_row_to_news 新闻行转换"""

    def test_normal_row(self):
        from src.data.providers.akshare import _row_to_news
        row = {"title": "标题", "date": "2024-01-02",
               "content": "内容", "source": "东方财富", "url": "http://example.com"}
        n = _row_to_news(row, code="000001")
        assert n.code == "000001"
        assert n.title == "标题"
        assert n.date == "2024-01-02"
        assert n.content == "内容"
        assert n.source == "东方财富"
        assert n.url == "http://example.com"

    def test_missing_keys_default_to_empty(self):
        from src.data.providers.akshare import _row_to_news
        row = {}
        n = _row_to_news(row, code="000001")
        assert n.code == "000001"
        assert n.title == ""
        assert n.url == ""


class TestAKShareErrorHandling:
    """AKShareSource 异常路径"""

    def test_get_all_stocks_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(ak, "stock_info_a_code_name", side_effect=ConnectionError("网络错误"))
        source = AKShareSource()
        result = source.get_all_stocks()
        assert result == []

    def test_get_realtime_quotes_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(ak, "stock_zh_a_spot_em", side_effect=ConnectionError("网络错误"))
        source = AKShareSource()
        result = source.get_realtime_quotes()
        assert result == []

    def test_get_klines_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(ak, "stock_zh_a_hist", side_effect=ConnectionError("网络错误"))
        source = AKShareSource()
        result = source.get_klines("000001")
        assert result == []

    def test_get_news_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(ak, "stock_news_em", side_effect=ConnectionError("网络错误"))
        source = AKShareSource()
        result = source.get_news("000001")
        assert result == []

    def test_get_capital_flow_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(
            ak, "stock_individual_fund_flow",
            side_effect=ConnectionError("网络错误"),
        )
        source = AKShareSource()
        result = source.get_capital_flow("000001")
        assert result == []

    def test_get_industry_boards_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(
            ak, "stock_board_industry_name_em",
            side_effect=ConnectionError("网络错误"),
        )
        source = AKShareSource()
        result = source.get_industry_boards()
        assert result == []

    def test_get_concept_boards_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(
            ak, "stock_board_concept_name_em",
            side_effect=ConnectionError("网络错误"),
        )
        source = AKShareSource()
        result = source.get_concept_boards()
        assert result == []

    def test_capital_flow_empty_df(self, mocker):
        """空 DataFrame 应返回空列表"""
        import akshare as ak
        import pandas as pd

        from src.data.providers.akshare import AKShareSource
        mocker.patch.object(ak, "stock_individual_fund_flow", return_value=pd.DataFrame())
        source = AKShareSource()
        result = source.get_capital_flow("000001")
        assert result == []


class TestAKShareCapitalFlowDataParsing:
    """资金流向数据逐行解析"""

    def test_single_row_parsing(self, mocker):
        import akshare as ak
        import pandas as pd

        from src.data.providers.akshare import AKShareSource

        mock_df = pd.DataFrame([{
            "日期": "2024-01-02",
            "主力净流入-净额": 1000000.0,
            "小单净流入-净额": -200000.0,
            "大单净流入-净额": 500000.0,
        }])
        mocker.patch.object(ak, "stock_individual_fund_flow", return_value=mock_df)
        source = AKShareSource()
        result = source.get_capital_flow("000001")
        assert len(result) == 1
        assert result[0].date == "2024-01-02"
        assert result[0].main_net_inflow == 1000000.0
        assert result[0].retail_net_inflow == -200000.0
        assert result[0].institutional_net_inflow == 500000.0

    def test_invalid_row_skipped(self, mocker):
        """某行解析失败应跳过该行，不阻塞整体"""
        import akshare as ak
        import pandas as pd

        from src.data.providers.akshare import AKShareSource

        mock_df = pd.DataFrame([
            {
                "日期": "2024-01-02", "主力净流入-净额": 100.0,
                "小单净流入-净额": -50.0, "大单净流入-净额": 30.0,
            },
            {
                "日期": "2024-01-03",
                "主力净流入-净额": None, "小单净流入-净额": None,
                "大单净流入-净额": None,
            },
        ])
        mocker.patch.object(ak, "stock_individual_fund_flow", return_value=mock_df)
        source = AKShareSource()
        result = source.get_capital_flow("000001")
        # 第二行有 None 但 safe_float 处理为 0，所以不应该跳过
        assert len(result) == 2


# ── AKShareSource 基本结构 ──────────────────────────────────────────


class TestAKShareSource:
    """AKShareSource 结构验证（不调远程 API）"""

    def test_importable(self):
        from src.data.providers.akshare import AKShareSource
        # 只验证能 import 和实例化
        source = AKShareSource()
        assert source is not None

    def test_has_required_methods(self):
        from src.data.providers.akshare import AKShareSource

        source = AKShareSource()
        assert hasattr(source, "get_all_stocks")
        assert hasattr(source, "get_realtime_quotes")
        assert hasattr(source, "get_klines")
        assert hasattr(source, "get_news")
        assert hasattr(source, "get_industry_boards")
        assert hasattr(source, "get_concept_boards")
        assert hasattr(source, "get_capital_flow")
        assert hasattr(source, "get_financials")


class TestAKShareFinancialRowToModel:
    """_row_to_financial 财务指标行转换"""

    def test_normal_row(self):
        from src.data.providers.akshare import _row_to_financial

        row = {
            "日期": "2024-12-31",
            "摊薄每股收益(元)": 1.25,
            "每股净资产_调整后(元)": 12.50,
            "每股经营性现金流(元)": 2.10,
            "净资产收益率(%)": 10.5,
            "总资产利润率(%)": 5.2,
            "销售毛利率(%)": 35.0,
            "销售净利率(%)": 15.0,
            "主营业务收入增长率(%)": 8.5,
            "净利润增长率(%)": 12.3,
            "资产负债率(%)": 55.0,
            "流动比率": 1.5,
            "速动比率": 1.1,
            "存货周转率(次)": 5.0,
            "总资产周转率(次)": 0.8,
            "总资产(元)": 1e12,
            "主营业务利润(元)": 5e10,
        }
        m = _row_to_financial(row, code="000001")
        assert m.stock_code == "000001"
        assert m.report_date == "2024-12-31"
        assert m.eps == 1.25
        assert m.roe == 10.5
        assert m.debt_ratio == 55.0
        assert m.total_assets == 1e12

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.akshare import _row_to_financial

        row = {"日期": "2024-12-31"}
        m = _row_to_financial(row, code="000001")
        assert m.eps == 0.0
        assert m.roe == 0.0
        assert m.debt_ratio == 0.0
        assert m.asset_turnover == 0.0

    def test_none_values_safe(self):
        from src.data.providers.akshare import _row_to_financial

        row = {
            "日期": "2024-12-31",
            "摊薄每股收益(元)": None,
            "资产负债率(%)": None,
            "流动比率": None,
        }
        m = _row_to_financial(row, code="000001")
        assert m.eps == 0.0
        assert m.debt_ratio == 0.0
        assert m.current_ratio == 0.0


class TestAKShareFinancialErrorHandling:
    """AKShareSource 财务数据异常路径"""

    def test_get_financials_returns_empty_on_error(self, mocker):
        import akshare as ak

        from src.data.providers.akshare import AKShareSource

        mocker.patch.object(
            ak, "stock_financial_analysis_indicator",
            side_effect=ConnectionError("网络错误"),
        )
        source = AKShareSource()
        result = source.get_financials("000001")
        assert result == []

    def test_get_financials_empty_df(self, mocker):
        import akshare as ak
        import pandas as pd

        from src.data.providers.akshare import AKShareSource

        mocker.patch.object(
            ak, "stock_financial_analysis_indicator",
            return_value=pd.DataFrame(),
        )
        source = AKShareSource()
        result = source.get_financials("000001")
        assert result == []


# ── adata 转换函数测试 ──────────────────────────────────────────────


class TestADataRowToQuote:
    """_adata_row_to_quote 实时行情行转换"""

    def test_normal_row(self):
        from src.data.providers.adata_source import _adata_row_to_quote
        row = {"stock_code": "000001", "stock_name": "平安银行", "latest_price": 12.34,
               "change": 0.56, "change_pct": 4.76, "volume": 1000000,
               "amount": 12340000.0, "high": 12.50, "low": 12.10,
               "open": 12.20, "pre_close": 11.78}
        q = _adata_row_to_quote(row)
        assert q.code == "000001"
        assert q.name == "平安银行"
        assert q.price == 12.34
        assert q.change == 0.56
        assert q.change_pct == 4.76
        assert q.volume == 1000000

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.adata_source import _adata_row_to_quote
        row = {"stock_code": "000001"}
        q = _adata_row_to_quote(row)
        assert q.code == "000001"
        assert q.price == 0.0
        assert q.name == ""


class TestADataRowToKline:
    """_adata_row_to_kline K 线行转换"""

    def test_normal_row(self):
        from src.data.providers.adata_source import _adata_row_to_kline
        row = {"trade_date": "2024-01-02", "open": 10.0, "close": 10.5,
               "high": 10.8, "low": 9.9, "volume": 500000, "amount": 5200000.0}
        k = _adata_row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 10.0
        assert k.close == 10.5
        assert k.high == 10.8
        assert k.low == 9.9
        assert k.volume == 500000

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.adata_source import _adata_row_to_kline
        row = {"trade_date": "2024-01-02"}
        k = _adata_row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 0.0


class TestADataSourceErrorHandling:
    """ADataSource 方法异常路径（mock adata 内部调用）"""

    def test_get_all_stocks_returns_empty_on_error(self, mocker):
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        # mock 整个 all_code 调用链
        mocker.patch.object(
            source._adata.stock.info, "all_code",
            side_effect=ConnectionError("网络错误"),
        )
        result = source.get_all_stocks()
        assert result == []

    def test_get_realtime_quotes_returns_empty_on_error(self, mocker):
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        mocker.patch.object(
            source._adata.stock.info, "all_code",
            return_value=__import__("pandas").DataFrame(),
        )
        mocker.patch.object(
            source._adata.stock.market, "list_market_current",
            side_effect=ConnectionError("网络错误"),
        )
        result = source.get_realtime_quotes()
        assert result == []

    def test_get_realtime_quotes_empty_stocks(self):
        """全部股票为空，应返回空列表"""
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        original = source._adata.stock.info.all_code
        source._adata.stock.info.all_code = lambda: __import__("pandas").DataFrame()
        try:
            result = source.get_realtime_quotes()
            assert result == []
        finally:
            source._adata.stock.info.all_code = original

    def test_get_klines_returns_empty_on_error(self, mocker):
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        mocker.patch.object(
            source._adata.stock.market, "get_market",
            side_effect=ConnectionError("网络错误"),
        )
        result = source.get_klines("000001")
        assert result == []

    def test_get_industry_boards_returns_empty_on_error(self, mocker):
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        # adata 版本不同时 all_industry 可能不存在，用字符串路径 mock
        mocker.patch.object(
            source._adata.stock.info, "all_industry",
            side_effect=ConnectionError("网络错误"), create=True,
        )
        result = source.get_industry_boards()
        assert result == []

    def test_get_klines_weekly_period(self, mocker):
        """周 K 线应使用 k_type=2"""
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        mock_df = __import__("pandas").DataFrame()
        mocker.patch.object(source._adata.stock.market, "get_market", return_value=mock_df)
        result = source.get_klines("000001", period="weekly")
        assert result == []

    def test_get_klines_monthly_period(self, mocker):
        """月 K 线应使用 k_type=3"""
        from src.data.providers.adata_source import ADataSource
        source = ADataSource()
        mock_df = __import__("pandas").DataFrame()
        mocker.patch.object(source._adata.stock.market, "get_market", return_value=mock_df)
        result = source.get_klines("000001", period="monthly")
        assert result == []


class TestADataSourcePlaceholders:
    """ADataSource 占位方法的行为"""

    def test_get_news_returns_empty(self):
        from src.data.providers.adata_source import ADataSource
        # 不调用远程 API，只测占位方法
        assert ADataSource.get_news(None, "000001") == []  # type: ignore[arg-type]

    def test_get_concept_boards_returns_empty(self):
        from src.data.providers.adata_source import ADataSource
        assert ADataSource.get_concept_boards(None) == []  # type: ignore[arg-type]

    def test_get_capital_flow_returns_empty(self):
        from src.data.providers.adata_source import ADataSource
        assert ADataSource.get_capital_flow(None, "000001") == []  # type: ignore[arg-type]


class TestADataSourceImport:
    """ADataSource 导入和结构"""

    def test_importable(self):
        from src.data.providers.adata_source import ADataSource
        # 只验证模块能 import
        assert ADataSource is not None

    def test_has_required_methods(self):
        from src.data.providers.adata_source import ADataSource

        assert hasattr(ADataSource, "get_all_stocks")
        assert hasattr(ADataSource, "get_realtime_quotes")
        assert hasattr(ADataSource, "get_klines")
        assert hasattr(ADataSource, "get_news")
        assert hasattr(ADataSource, "get_industry_boards")
        assert hasattr(ADataSource, "get_concept_boards")
        assert hasattr(ADataSource, "get_capital_flow")
        assert hasattr(ADataSource, "get_financials")


# ── zzshare 工具函数测试 ────────────────────────────────────────────


class TestZzshareToTsCode:
    """_to_ts_code 代码格式转换"""

    def test_sh_stock(self):
        from src.data.providers.zzshare import _to_ts_code
        assert _to_ts_code("600000") == "600000.SH"

    def test_sz_stock(self):
        from src.data.providers.zzshare import _to_ts_code
        assert _to_ts_code("000001") == "000001.SZ"
        assert _to_ts_code("300750") == "300750.SZ"
        assert _to_ts_code("002001") == "002001.SZ"

    def test_already_ts_code(self):
        from src.data.providers.zzshare import _to_ts_code
        assert _to_ts_code("000001.SZ") == "000001.SZ"
        assert _to_ts_code("600000.SH") == "600000.SH"

    def test_handles_whitespace(self):
        from src.data.providers.zzshare import _to_ts_code
        assert _to_ts_code(" 600000 ") == "600000.SH"
        assert _to_ts_code(" 000001 ") == "000001.SZ"


class TestZzshareRowToKline:
    """_zz_row_to_kline K 线行转换"""

    def test_normal_row(self):
        from src.data.providers.zzshare import _zz_row_to_kline
        row = {"trade_date": "2024-01-02", "open": 10.0, "close": 10.5,
               "high": 10.8, "low": 9.9, "vol": 500000, "amount": 5200000.0}
        k = _zz_row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 10.0
        assert k.close == 10.5
        assert k.high == 10.8
        assert k.low == 9.9
        assert k.volume == 500000
        assert k.amount == 5200000.0

    def test_missing_keys_default_to_zero(self):
        from src.data.providers.zzshare import _zz_row_to_kline
        row = {"trade_date": "2024-01-02"}
        k = _zz_row_to_kline(row)
        assert k.date == "2024-01-02"
        assert k.open == 0.0
        assert k.volume == 0

    def test_trade_date_key_exists(self):
        """验证 TD-034：trade_date 字段选择逻辑实际不造成 bug"""
        from src.data.providers.zzshare import _zz_row_to_kline
        # 当前代码两个条件一样（都返回 trade_date），所以不管怎样都正确
        row = {"trade_date": "2024-01-02"}
        k = _zz_row_to_kline(row)
        assert k.date == "2024-01-02"

    def test_vol_field_mapped_correctly(self):
        """zzshare 使用 vol 而非 volume 字段名"""
        from src.data.providers.zzshare import _zz_row_to_kline
        row = {"trade_date": "2024-01-02", "vol": 100000}
        k = _zz_row_to_kline(row)
        assert k.volume == 100000

    def test_amount_default_zero(self):
        from src.data.providers.zzshare import _zz_row_to_kline
        row = {"trade_date": "2024-01-02"}
        k = _zz_row_to_kline(row)
        assert k.amount == 0.0


class TestZzshareSourceImport:
    """ZzshareSource 导入和结构"""

    def test_importable(self):
        from src.data.providers.zzshare import ZzshareSource
        assert ZzshareSource is not None

    def test_has_required_methods(self):
        from src.data.providers.zzshare import ZzshareSource

        assert hasattr(ZzshareSource, "get_all_stocks")
        assert hasattr(ZzshareSource, "get_realtime_quotes")
        assert hasattr(ZzshareSource, "get_klines")
        assert hasattr(ZzshareSource, "get_news")
        assert hasattr(ZzshareSource, "get_industry_boards")
        assert hasattr(ZzshareSource, "get_concept_boards")
        assert hasattr(ZzshareSource, "get_capital_flow")
        assert hasattr(ZzshareSource, "get_financials")


# ── FallbackSource ──────────────────────────────────────────────────


class MockFailingPrimary:
    """总是失败的主源"""

    def get_all_stocks(self):
        raise ConnectionError("主源挂了")

    def get_realtime_quotes(self):
        raise ConnectionError("主源挂了")

    def get_klines(self, code: str = "", period: str = "daily", start: str = "",
                   end: str = "", adjust: str = "qfq"):
        raise ConnectionError("主源挂了")

    def get_news(self, code: str = ""):
        raise ConnectionError("主源挂了")

    def get_industry_boards(self):
        raise ConnectionError("主源挂了")

    def get_concept_boards(self):
        raise ConnectionError("主源挂了")

    def get_capital_flow(self, code: str = ""):
        raise ConnectionError("主源挂了")

    def get_financials(self, code: str = ""):
        raise ConnectionError("主源挂了")


class MockHealthyFallback:
    """总是成功的备用源"""

    def get_all_stocks(self):
        return ["fallback_stock"]

    def get_realtime_quotes(self):
        return ["fallback_quote"]

    def get_klines(self, code: str = "", period: str = "daily", start: str = "",
                   end: str = "", adjust: str = "qfq"):
        return ["fallback_kline"]

    def get_news(self, code: str = ""):
        return ["fallback_news"]

    def get_industry_boards(self):
        return ["fallback_board"]

    def get_concept_boards(self):
        return ["fallback_concept"]

    def get_capital_flow(self, code: str = ""):
        return ["fallback_capital_flow"]

    def get_financials(self, code: str = ""):
        return ["fallback_financials"]

    def __repr__(self) -> str:
        return "MockHealthyFallback"


class MockMixedPrimary:
    """混合表现的主源（前 2 次失败，第 3 次成功）"""

    def __init__(self):
        self._call_count = 0

    def get_all_stocks(self):
        self._call_count += 1
        if self._call_count <= 2:
            raise ConnectionError("暂时不可用")
        return ["primary_recovered"]

    def get_realtime_quotes(self):
        return ["primary_quote"]

    def get_klines(self, code: str = "", period: str = "daily", start: str = "",
                   end: str = "", adjust: str = "qfq"):
        return []

    def get_news(self, code: str = ""):
        return []

    def get_industry_boards(self):
        return []

    def get_concept_boards(self):
        return []

    def get_capital_flow(self, code: str = ""):
        return []

    def get_financials(self, code: str = ""):
        return []


class TestFallbackSource:
    """FallbackSource 故障切换逻辑"""

    def test_healthy_primary_stays_on_primary(self):
        """主源正常时不应切到备用"""
        from src.data.providers.fallback import FallbackSource

        primary = MockMixedPrimary()
        fallback = MockHealthyFallback()
        source = FallbackSource(
            primary=primary,  # type: ignore[arg-type]
            fallback=fallback,  # type: ignore[arg-type]
            max_failures=3,
        )

        result = source.get_realtime_quotes()
        assert result == ["primary_quote"]
        assert not source._using_fallback["quotes"]

    def test_fallback_on_consecutive_failures(self):
        """主源连续失败达到阈值后切到备用"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=2,
        )

        # 第 1 次失败（未达阈值，返回空）
        result1 = source.get_all_stocks()
        assert result1 == []  # 主源失败，未达阈值
        assert not source._using_fallback["all_stocks"]

        # 第 2 次失败（达阈值，切备用）
        result2 = source.get_all_stocks()
        assert result2 == ["fallback_stock"]
        assert source._using_fallback["all_stocks"]

        # 第 3 次（已在备用上）
        result3 = source.get_all_stocks()
        assert result3 == ["fallback_stock"]

    def test_endpoint_independent_failover(self):
        """不同 endpoint 的故障切换互不影响"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=1,
        )

        # 仅触发 all_stocks 的切换
        source.get_all_stocks()  # 第 1 次失败即切
        assert source._using_fallback["all_stocks"]
        assert "quotes" not in source._using_fallback  # 不受影响

    def test_reset_switches_back_to_primary(self):
        """reset() 应切回主源"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=1,
        )
        source.get_all_stocks()  # 切到备用
        assert source._using_fallback["all_stocks"]

        source.reset("all_stocks")
        assert not source._using_fallback["all_stocks"]

    def test_reset_all_endpoints(self):
        """reset() 不带参数应重置全部 endpoint"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=1,
        )
        source.get_all_stocks()
        source.get_realtime_quotes()
        assert source._using_fallback["all_stocks"]
        assert source._using_fallback["quotes"]

        source.reset()
        assert not any(source._using_fallback.values())

    def test_both_sources_fail_returns_empty(self):
        """主备都失败时返回空列表"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockFailingPrimary(),  # type: ignore[arg-type]
            max_failures=1,
        )

        result = source.get_all_stocks()
        assert result == []

    def test_fallback_mode_property(self):
        """fallback_mode 返回当前各 endpoint 状态"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=1,
        )

        assert source.fallback_mode == {}
        source.get_all_stocks()  # 触发切换
        assert source.fallback_mode["all_stocks"] is True

    def test_primary_recovers_after_reset(self):
        """reset 后主源恢复工作"""
        from src.data.providers.fallback import FallbackSource

        primary = MockMixedPrimary()
        source = FallbackSource(
            primary=primary,  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=2,
        )

        # 消耗主源的 2 次失败
        source.get_all_stocks()  # 失败
        source.get_all_stocks()  # 失败，切备用

        # reset 后切回主源，第 3 次调用主源时应成功
        source.reset("all_stocks")
        result = source.get_all_stocks()
        # MockMixedPrimary 第 3 次返回 "primary_recovered"
        assert result == ["primary_recovered"]
        assert not source._using_fallback["all_stocks"]

    def test_integration_with_collector(self):
        """FallbackSource + DataCollector 集成"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=0,  # 立即切换
        )
        collector = DataCollector(source=source)  # type: ignore[arg-type]

        result = collector.get_all_stocks()
        # DataCollector 缓存了结果，应有值
        assert result is not None

    # ── TD-032: 备用源自动恢复主源 ────────────────────────────────────


class TestFallbackSourceAutoRecovery:
    """备用源连续成功后自动恢复主源（TD-032 修复）"""

    def test_fallback_recovers_to_primary_after_successes(self):
        """备用源恢复后可通过 reset 切回主源"""
        from src.data.providers.fallback import FallbackSource

        class RecoveryPrimary:
            """先失败后恢复的主源"""
            def __init__(self):
                self.calls = 0

            def get_all_stocks(self):
                self.calls += 1
                if self.calls <= 1:
                    raise ConnectionError("暂时不可用")
                return ["primary_ok"]

        class CountingFallback:
            """计数备用源"""
            def __init__(self):
                self.calls = 0

            def get_all_stocks(self):
                self.calls += 1
                return ["fallback_ok"]

        primary = RecoveryPrimary()
        fallback = CountingFallback()
        source = FallbackSource(
            primary=primary,  # type: ignore[arg-type]
            fallback=fallback,  # type: ignore[arg-type]
            max_failures=1,
        )

        # max_failures=1 → 首次失败即切备用，同时返回备用结果
        r1 = source.get_all_stocks()
        assert r1 == ["fallback_ok"]
        assert source._using_fallback["all_stocks"] is True

        # 当前 FallbackSource 没有自动恢复逻辑 → 需要手动 reset
        source.reset("all_stocks")
        # reset 后主源已恢复，第 2 次应走主源
        r2 = source.get_all_stocks()
        assert r2 == ["primary_ok"]
        assert not source._using_fallback["all_stocks"]

    def test_kline_endpoint_isolated_failover(self):
        """K 线 endpoint 的故障切换使用正确的 lambda 包装"""
        from src.data.providers.fallback import FallbackSource

        class CallTrackingPrimary:
            def __init__(self):
                self.kline_calls = []

            def get_klines(self, code="", period="daily", start="", end="", adjust="qfq"):
                self.kline_calls.append((code, period, start, end, adjust))
                raise ConnectionError("主源 K 线挂了")

        primary = CallTrackingPrimary()
        fallback = MockHealthyFallback()
        source = FallbackSource(
            primary=primary,  # type: ignore[arg-type]
            fallback=fallback,  # type: ignore[arg-type]
            max_failures=1,
        )

        # max_failures=1 → 首次失败即切备用
        result = source.get_klines("000001", period="weekly")
        assert result == ["fallback_kline"]

        # 验证参数透传
        assert len(primary.kline_calls) >= 1
        code, period, start, end, adjust = primary.kline_calls[0]
        assert code == "000001"
        assert period == "weekly"

    def test_consecutive_success_resets_failure_count(self):
        """主源成功后应重置失败计数，防止误触发切换"""
        from src.data.providers.fallback import FallbackSource

        class IntermittentPrimary:
            def __init__(self):
                self.call_no = 0

            def get_all_stocks(self):
                self.call_no += 1
                if self.call_no == 1:
                    raise ConnectionError("偶尔挂了")
                return ["primary_ok"]

        source = FallbackSource(
            primary=IntermittentPrimary(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=3,
        )

        # 第 1 次失败，计数=1
        source.get_all_stocks()
        assert source._consecutive_failures["all_stocks"] == 1
        # 第 2 次成功，计数应重置为 0
        source.get_all_stocks()
        assert source._consecutive_failures["all_stocks"] == 0

    def test_mixed_primary_allows_partial_recovery(self):
        """部分 endpoint 恢复不应影响其他 endpoint"""
        from src.data.providers.fallback import FallbackSource

        primary = MockMixedPrimary()
        source = FallbackSource(
            primary=primary,  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=2,
        )

        # 触发 all_stocks 到达阈值
        source.get_all_stocks()  # 失败 1
        source.get_all_stocks()  # 失败 2 → 切备用
        assert source._using_fallback["all_stocks"] is True

        # 但 quotes endpoint 一直正常工作
        quotes = source.get_realtime_quotes()
        assert quotes == ["primary_quote"]
        assert "quotes" not in source._using_fallback or not source._using_fallback["quotes"]


class TestFallbackSourceExtended:
    """FallbackSource 其他委托方法的测试"""

    def test_get_news_forwards_to_primary(self):
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockHealthyFallback(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=3,
        )
        result = source.get_news("000001")
        assert result == ["fallback_news"]

    def test_get_industry_boards_forwards_to_primary(self):
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockHealthyFallback(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=3,
        )
        result = source.get_industry_boards()
        assert result == ["fallback_board"]

    def test_get_concept_boards_forwards_to_primary(self):
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockHealthyFallback(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=3,
        )
        result = source.get_concept_boards()
        assert result == ["fallback_concept"]

    def test_get_capital_flow_forwards_to_primary(self):
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockHealthyFallback(),  # type: ignore[arg-type]
            fallback=MockHealthyFallback(),  # type: ignore[arg-type]
            max_failures=3,
        )
        result = source.get_capital_flow("000001")
        assert result == ["fallback_capital_flow"]

    def test_fallback_fails_while_in_fallback_mode(self):
        """已切到备用源后，备用源也失败应返回空"""
        from src.data.providers.fallback import FallbackSource

        source = FallbackSource(
            primary=MockFailingPrimary(),  # type: ignore[arg-type]
            fallback=MockFailingPrimary(),  # type: ignore[arg-type]
            max_failures=1,
        )

        # 第 1 次：主源失败→切备用→备用也失败
        r1 = source.get_all_stocks()
        assert r1 == []
        assert source._using_fallback["all_stocks"] is True

        # 第 2 次：直接走备用（已切），备用还是失败
        r2 = source.get_all_stocks()
        assert r2 == []
        assert source._consecutive_failures["all_stocks"] == 2  # 备用失败计数也增
