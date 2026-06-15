"""回测引擎数据契约 —— Pydantic 模型定义

遵循 ADR-001/008 的数据契约规范，与 trader/risk 模块一致的 Pydantic 模式。
定义了 5 个核心数据模型：

1. BacktestConfig — 回测配置
2. TradeRecord — 单笔交易记录
3. PortfolioSnapshot — 每日持仓快照
4. PerformanceMetrics — 绩效指标体系
5. BacktestReport — 完整回测报告
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class BacktestConfig(BaseModel):
    """回测配置

    定义回测运行的参数：初始资金、交易成本、仓位限制。

    Attributes:
        initial_capital: 初始资金（元）
        commission_rate: 手续费率（如万三 = 0.0003）
        slippage: 滑点比例（如千一 = 0.001）
        max_single_position: 单票仓位上限（0.0–1.0）
    """

    initial_capital: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage: float = 0.001
    max_single_position: float = 0.2


class TradeRecord(BaseModel):
    """单笔交易记录

    记录一次完整的交易从入场到出场的过程。
    供回测引擎填充，也可在回测前人工构造 TradeSignal 再由引擎转为 TradeRecord。

    Attributes:
        ticker: 股票代码
        direction: 交易方向（buy / sell）
        entry_date: 入场日期（YYYY-MM-DD）
        exit_date: 出场日期（YYYY-MM-DD）
        entry_price: 入场价格
        exit_price: 出场价格
        quantity: 成交股数
        position_pct: 该笔交易占总资金比例（0.0–1.0）
        pnl: 盈亏金额（元）
        pnl_pct: 盈亏百分比（相对投入资金）
        holding_days: 持仓天数
        exit_reason: 出场原因（"止盈" / "止损" / "信号反转" / "持有到期"）
        trade_plan: 原始交易计划快照（序列化 dict，可选）
    """

    ticker: str = ""
    direction: str = "buy"
    entry_date: str = ""
    exit_date: str = ""
    entry_price: float = 0.0
    exit_price: float = 0.0
    quantity: int = 0
    position_pct: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    exit_reason: str = ""
    trade_plan: dict = Field(default_factory=dict)


class PortfolioSnapshot(BaseModel):
    """每日持仓快照

    记录回测过程中每一天的资产状态，用于构建净值曲线和计算回撤。

    Attributes:
        date: 快照日期（YYYY-MM-DD）
        total_value: 总资产（现金 + 持仓市值）
        cash: 现金余额
        position_value: 持仓市值
        daily_return: 当日收益率
        cumulative_return: 累计收益率（相对初始资金）
        drawdown: 当前回撤（从峰值到当前的最大跌幅比例）
    """

    date: str = ""
    total_value: float = 0.0
    cash: float = 0.0
    position_value: float = 0.0
    daily_return: float = 0.0
    cumulative_return: float = 0.0
    drawdown: float = 0.0


class PerformanceMetrics(BaseModel):
    """绩效指标体系

    计算交易策略的历史表现指标。所有比率类指标以小数形式表示
    （如 15% = 0.15），非百分比。

    Attributes:
        total_return: 总收益率
        annual_return: 年化收益率
        max_drawdown: 最大回撤（正数表示跌幅，如 0.05 = 回撤 5%）
        sharpe_ratio: 夏普比率（年化）
        win_rate: 胜率（0.0–1.0）
        profit_factor: 盈亏比（总盈利/总亏损，>1 为盈利）
        total_trades: 总交易次数
        winning_trades: 盈利交易次数
        losing_trades: 亏损交易次数
        avg_holding_days: 平均持仓天数
        cagr: 复合年增长率
    """

    total_return: float = 0.0
    annual_return: float = 0.0
    max_drawdown: float = 0.0
    sharpe_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_holding_days: float = 0.0
    cagr: float = 0.0


class BacktestReport(BaseModel):
    """完整回测报告

    回测引擎的最终输出。包含配置、绩效指标、交易明细和净值曲线。

    Attributes:
        config: 回测配置
        metrics: 绩效指标
        trades: 所有交易记录
        equity_curve: 每日净值曲线
        start_date: 回测开始日期
        end_date: 回测结束日期
        ticker: 回测股票代码
        total_days: 回测总天数
    """

    config: BacktestConfig = Field(default_factory=BacktestConfig)
    metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    trades: list[TradeRecord] = Field(default_factory=list)
    equity_curve: list[PortfolioSnapshot] = Field(default_factory=list)
    start_date: str = ""
    end_date: str = ""
    ticker: str = ""
    total_days: int = 0
