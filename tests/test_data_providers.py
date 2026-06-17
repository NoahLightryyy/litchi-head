"""数据源 Provider 层单元测试

覆盖：
1. AKShareSource 基本结构
2. ADataSource / ZzshareSource ImportError 处理
3. FallbackSource 故障自动切换逻辑
4. MockDataSource 注入 DataCollector
"""

from src.data.collector import DataCollector
from src.data.providers.base import DataSource


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


# ── ADataSource ImportError ─────────────────────────────────────────


class TestADataSource:
    """adata 未安装时应抛 ImportError"""

    def test_import_error_when_not_installed(self):
        """adata 不是必须依赖，未安装时抛明确的 ImportError"""
        try:
            import adata  # noqa: F401
            # adata 已安装，跳过此测试
            pass
        except ImportError:
            from src.data.providers.adata_source import ADataSource

            try:
                ADataSource()
                assert False, "应抛出 ImportError"
            except ImportError:
                pass  # 期望行为

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


# ── ZzshareSource ImportError ───────────────────────────────────────


class TestZzshareSource:
    """zzshare 未安装时应抛 ImportError"""

    def test_import_error_when_not_installed(self):
        try:
            import zzshare  # noqa: F401
            pass
        except ImportError:
            from src.data.providers.zzshare import ZzshareSource

            try:
                ZzshareSource()
                assert False, "应抛出 ImportError"
            except ImportError:
                pass  # 期望行为

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
