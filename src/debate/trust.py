"""M3 信任度评分模块

信任度评分 —— 追踪每位 Agent 的历史预测 vs 实际市场结果，生成信任度画像。

核心功能：
  1. AgentOutcome 记录 — 连接 Agent 的预测输出与市场实际结果
  2. TrustTracker 累积统计 — 方向准确率/置信度校准/评分偏差/趋势
  3. TrustReport 查询 — 获取某 Agent 的完整信任度画像

与 M2 反思闭环的关系：
  · M2（反思）—— 定性分析：为什么错了？教训是什么？
  · M3（信任度）—— 定量追踪：谁更可信？偏差有多大？
  · M2 的 ReflectionRecord 面向一次辩论的共识，M3 面向每个 Agent 个体

用法：
    tracker = TrustTracker(memory_store=store)

    # 记录一次预测结果
    tracker.record_outcome(
        analysis=agent_analysis_instance,
        actual_direction="Bullish",
        actual_price_change_pct=+3.5,
    )

    # 查询某 Agent 的信任度画像
    report = await tracker.get_trust_report("master.buffett")
    print(report.win_rate)           # 0.68
    print(report.calibration_score)  # 0.12 (Brier score, 0=完美)

    # 批量记录（回测结束后）
    tracker.record_outcomes(analyses=[...], outcomes=[...])
"""

from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, model_validator

from src.memory.store import MemoryStore

logger = logging.getLogger(__name__)

# ── 数据模型 ──────────────────────────────────────────────────


class AgentOutcome(BaseModel):
    """单次 Agent 预测 vs 实际结果记录

    桥接 AgentAnalysis（预测）与市场实际结果，是 M3 信任度计算的基础数据单元。
    每次赛后（回测或真实市场反馈）生成一条记录。

    Attributes:
        agent_name: Agent 标识（如 "master.buffett" / "analyst.fundamental"）
        skill_id: Agent 的 skill_id（如 "buffett"）
        skill_name: Agent 的 skill_name（如 "巴菲特"）
        session_id: 所属辩论会话标识
        stock_code: 股票代码
        sector: 板块标识（如 "食品饮料" / "新能源"），用于按场景校准信任度
        decision_date: 决策日期（ISO 格式字符串）
        evaluation_date: 评估日期
        # ── 预测值（来自 AgentAnalysis）──
        predicted_direction: Agent 预测的方向（Bullish/Bearish/Neutral）
        predicted_score: Agent 给出的评分（1-100）
        predicted_confidence: Agent 给出的置信度（0.0-1.0）
        predicted_rating: Agent 给出的评级文本
        # ── 实际值（来自 ActualOutcome / 回测）──
        actual_direction: 实际市场方向（Bullish/Bearish/Neutral）
        actual_price_change_pct: 实际价格变动百分比
        is_correct: 方向判断是否正确
    """

    agent_name: str
    skill_id: str = ""
    skill_name: str = ""
    session_id: str = ""
    stock_code: str = ""
    sector: str = ""
    decision_date: str = ""
    evaluation_date: str = ""
    # ── 预测值 ──
    predicted_direction: str = "Neutral"
    predicted_score: int = 0
    predicted_confidence: float = 0.0
    predicted_rating: str = ""
    # ── 实际值 ──
    actual_direction: str = "Neutral"
    actual_price_change_pct: float = 0.0
    # ── 结果 ──
    is_correct: bool = False

    @model_validator(mode="after")
    def _derive_is_correct(self) -> "AgentOutcome":
        """自动从 predicted_direction 和 actual_direction 推导 is_correct"""
        self.is_correct = self.predicted_direction == self.actual_direction
        return self


class AgentTrustMetrics(BaseModel):
    """Agent 的累积信任度指标

    基于该 Agent 所有历史 AgentOutcome 计算的统计量。
    由 TrustTracker._compute_metrics() 生成，不可直接构造。

    Attributes:
        total_samples: 总样本数
        win_rate: 方向准确率（0.0-1.0）
        bullish_win_rate: 看涨时的准确率（充足样本时有效）
        bearish_win_rate: 看跌时的准确率（充足样本时有效）
        neutral_win_rate: 中性时的准确率
        sector_win_rates: 按板块统计的方向准确率
        sector_sample_counts: 每个板块的样本数
        # ── 置信度校准 ──
        brier_score: Brier score（0=完美，1=最差），校准程度
        confidence_bias: 置信度偏差（正=过度自信，负=过于保守）
        calibration_curve: 校准数据点 [{"bucket": 0-9, "acc": 0.5}, ...]
        # ── 评分偏差 ──
        avg_score_error: 评分 vs 实际表现的均绝对偏差（归一化）
        optimism_bias: 乐观偏差（正=持续高估）
        # ── 趋势 ──
        recent_win_rate: 最近 N 次的方向准确率
        trend_direction: 趋势方向（"improving" / "declining" / "stable"）
        recent_count: 最近窗口的样本数
    """

    total_samples: int = 0
    win_rate: float = 0.0
    bullish_win_rate: float = 0.0
    bearish_win_rate: float = 0.0
    neutral_win_rate: float = 0.0
    sector_win_rates: dict[str, float] = Field(default_factory=dict)
    sector_sample_counts: dict[str, int] = Field(default_factory=dict)
    # ── 校准 ──
    brier_score: float = 0.0
    confidence_bias: float = 0.0
    calibration_curve: list[dict[str, float]] = Field(default_factory=list)
    # ── 评分偏差 ──
    avg_score_error: float = 0.0
    optimism_bias: float = 0.0
    # ── 趋势 ──
    recent_win_rate: float = 0.0
    trend_direction: str = "stable"
    recent_count: int = 0


class TrustReport(BaseModel):
    """信任度画像（面向人类可读 + 机器可消费）

    由 TrustTracker.get_trust_report() 返回，包含结构化信任度指标
    和可读摘要文本。

    Attributes:
        agent_name: Agent 名称
        skill_name: Agent 的可读名称
        metrics: 累积信任度指标
        summary: 一句话摘要（机器生成的定性描述）
        sample_direction_breakdown: 各方向样本数
        is_reliable: 是否有足够样本得出统计结论（>= 5 样本）
        last_updated: 最近一次记录的时间戳
    """

    agent_name: str = ""
    skill_name: str = ""
    metrics: AgentTrustMetrics = Field(default_factory=AgentTrustMetrics)
    summary: str = ""
    sample_direction_breakdown: dict[str, int] = Field(default_factory=dict)
    is_reliable: bool = False
    last_updated: str = ""


# ── 内部数据结构（不可变快照） ─────────────────────────────


@dataclass
class _AgentBuffer:
    """单个 Agent 的内存中累积数据（未持久化前）

    用于在 _compute_metrics 之前暂存最近更新的样本。
    每次 TrustTracker._flush() 时写入 MemoryStore。
    """

    outcomes: list[AgentOutcome] = field(default_factory=list)
    dirty: bool = False


# ── 核心常量 ──────────────────────────────────────────────────

_RECENT_WINDOW = 10  # 趋势检测用的最近样本窗口
_CALIBRATION_BUCKETS = 10  # 校准曲线的置信度分段数
_MIN_RELIABLE_SAMPLES = 5  # 最小可靠样本数
_TRUST_NAMESPACE = ("trust", "debate")  # MemoryStore 命名空间


# ── TrustTracker ──────────────────────────────────────────────


class TrustTracker:
    """信任度追踪器 —— 记录/查询/统计 Agent 历史表现

    纯数学统计（零 LLM 调用），使用 MemoryStore 持久化。
    数据不足时安全降级（返回默认值）。

    线程安全：不保存跨调用状态（每次 _flush 后清空内存缓存）。
    """

    def __init__(self, memory_store: MemoryStore | None = None) -> None:
        """初始化信任度追踪器

        Args:
            memory_store: 记忆存储实例（可选）。不提供时仅内存运行。
        """
        self._store = memory_store
        # 内存暂存区：agent_name → _AgentBuffer
        self._buffers: dict[str, _AgentBuffer] = {}

    # ── 公开 API ─────────────────────────────────────────────

    def record_outcome(
        self,
        agent_name: str,
        predicted_direction: str,
        predicted_score: int,
        predicted_confidence: float,
        actual_direction: str,
        actual_price_change_pct: float,
        predicted_rating: str = "",
        skill_id: str = "",
        skill_name: str = "",
        session_id: str = "",
        stock_code: str = "",
        sector: str = "",
        decision_date: str = "",
        evaluation_date: str = "",
    ) -> None:
        """记录一次 Agent 预测 vs 实际结果

        Args:
            agent_name: Agent 标识
            predicted_direction: 预测方向（Bullish/Bearish/Neutral）
            predicted_score: 预测评分（1-100）
            predicted_confidence: 预测置信度（0.0-1.0）
            actual_direction: 实际方向（Bullish/Bearish/Neutral）
            actual_price_change_pct: 实际价格变动百分比
            predicted_rating: Agent 给出的评级文本
            skill_id: Agent 的 skill_id
            skill_name: Agent 的 skill_name
            session_id: 所属辩论会话标识
            stock_code: 股票代码
            sector: 板块标识，用于按板块胜率校准权重
            decision_date: 决策日期
            evaluation_date: 评估日期
        """
        # 规范化方向值
        pred_dir = (
            predicted_direction
            if predicted_direction in ("Bullish", "Bearish", "Neutral")
            else "Neutral"
        )
        actual_dir = (
            actual_direction
            if actual_direction in ("Bullish", "Bearish", "Neutral")
            else "Neutral"
        )

        is_correct = pred_dir == actual_dir

        outcome = AgentOutcome(
            agent_name=agent_name,
            skill_id=skill_id,
            skill_name=skill_name,
            session_id=session_id,
            stock_code=stock_code,
            sector=sector,
            decision_date=decision_date,
            evaluation_date=evaluation_date,
            predicted_direction=pred_dir,
            predicted_score=predicted_score,
            predicted_confidence=predicted_confidence,
            predicted_rating=predicted_rating,
            actual_direction=actual_dir,
            actual_price_change_pct=actual_price_change_pct,
            is_correct=is_correct,
        )

        # 存入内存缓存
        if agent_name not in self._buffers:
            self._buffers[agent_name] = _AgentBuffer()
        self._buffers[agent_name].outcomes.append(outcome)
        self._buffers[agent_name].dirty = True

    def record_outcome_from_analysis(
        self,
        agent_name: str,
        score: int,
        confidence: float,
        direction: str,
        actual_direction: str,
        actual_price_change_pct: float,
        rating: str = "",
        skill_id: str = "",
        skill_name: str = "",
        session_id: str = "",
        stock_code: str = "",
        sector: str = "",
        decision_date: str = "",
        evaluation_date: str = "",
    ) -> None:
        """从 AgentAnalysis 字段直接记录（便捷包装）

        Args:
            agent_name: Agent 标识
            score: AgentAnalysis.score
            confidence: AgentAnalysis.confidence
            direction: AgentAnalysis.direction
            actual_direction: 实际市场方向
            actual_price_change_pct: 实际价格变动百分比
            rating: AgentAnalysis.rating
            skill_id: AgentAnalysis.skill_id
            skill_name: AgentAnalysis.skill_name
            session_id: 会话标识
            stock_code: 股票代码
            sector: 板块标识
            decision_date: 决策日期
            evaluation_date: 评估日期
        """
        direction = (
            direction if direction in ("Bullish", "Bearish", "Neutral") else "Neutral"
        )
        self.record_outcome(
            agent_name=agent_name,
            predicted_direction=direction,
            predicted_score=score,
            predicted_confidence=confidence,
            predicted_rating=rating,
            actual_direction=actual_direction,
            actual_price_change_pct=actual_price_change_pct,
            skill_id=skill_id,
            skill_name=skill_name,
            session_id=session_id,
            stock_code=stock_code,
            sector=sector,
            decision_date=decision_date,
            evaluation_date=evaluation_date,
        )

    async def get_trust_report(self, agent_name: str) -> TrustReport:
        """查询某 Agent 的信任度画像

        优先从 MemoryStore 加载已有记录，叠加内存中未持久化的新样本。

        Args:
            agent_name: Agent 标识

        Returns:
            完整信任度画像（数据不足时返回默认值，is_reliable=False）
        """
        # 1. 从 MemoryStore 加载持久化的历史记录
        stored_outcomes: list[AgentOutcome] = []
        if self._store:
            stored_outcomes = await self._load_outcomes(agent_name)

        # 2. 合并内存中未持久化的新样本
        pending: list[AgentOutcome] = []
        if agent_name in self._buffers:
            pending = list(self._buffers[agent_name].outcomes)

        all_outcomes = stored_outcomes + pending

        if not all_outcomes:
            return TrustReport(agent_name=agent_name, is_reliable=False)

        # 3. 计算指标
        metrics = self._compute_metrics(all_outcomes)

        # 4. 方向分布
        direction_count: dict[str, int] = {}
        for o in all_outcomes:
            direction_count[o.predicted_direction] = (
                direction_count.get(o.predicted_direction, 0) + 1
            )

        # 5. 摘要
        summary = self._generate_summary(
            agent_name=agent_name,
            metrics=metrics,
        )

        skill_name = ""
        if all_outcomes:
            skill_name = all_outcomes[-1].skill_name or ""

        return TrustReport(
            agent_name=agent_name,
            skill_name=skill_name,
            metrics=metrics,
            summary=summary,
            sample_direction_breakdown=direction_count,
            is_reliable=metrics.total_samples >= _MIN_RELIABLE_SAMPLES,
            last_updated=(
                all_outcomes[-1].evaluation_date
                if all_outcomes[-1].evaluation_date
                else ""
            ),
        )

    async def flush(self) -> None:
        """将内存缓存中的未持久化记录写入 MemoryStore

        应在批量记录完成后调用，或在会话结束前调用。
        MemoryStore 不存在时静默跳过。
        """
        if not self._store:
            return

        for agent_name, buffer in self._buffers.items():
            if not buffer.dirty or not buffer.outcomes:
                continue

            # 加载已有记录
            existing = await self._load_outcomes(agent_name)

            # 合并（去重：使用 session_id + stock_code + sector 去重）
            seen: set[str] = set()
            for o in existing:
                seen.add(_outcome_dedupe_key(o))
            new_records = [
                o
                for o in buffer.outcomes
                if _outcome_dedupe_key(o) not in seen
            ]

            if not new_records:
                buffer.dirty = False
                continue

            # 合并并保存
            merged = existing + new_records
            try:
                await self._store.put(
                    key=agent_name,
                    value=[o.model_dump() for o in merged],
                    namespace=_TRUST_NAMESPACE,
                )
                buffer.dirty = False
            except Exception as e:
                logger.warning("写入信任度记录失败: agent=%s, err=%s", agent_name, e)

    async def get_all_agent_names(self) -> list[str]:
        """获取有记录的 Agent 名称列表

        Returns:
            有信任度记录的 Agent 名称列表
        """
        names: set[str] = set(self._buffers.keys())
        if self._store:
            try:
                items = await self._store.search(
                    namespace=_TRUST_NAMESPACE,
                    query="",
                    k=100,
                )
                for item in items:
                    if isinstance(item.value, dict) and "agent_name" in item.value:
                        names.add(str(item.value["agent_name"]))
            except Exception as e:
                logger.warning("读取信任度记录失败，仅返回缓存数据: err=%s", e)
        return sorted(names)

    # ── 内部方法 ──────────────────────────────────────────────

    async def _load_outcomes(
        self, agent_name: str
    ) -> list[AgentOutcome]:
        """从 MemoryStore 加载某 Agent 的历史记录

        Args:
            agent_name: Agent 标识

        Returns:
            AgentOutcome 列表（无记录时返回空列表）
        """
        if not self._store:
            return []

        try:
            item = await self._store.get(
                key=agent_name,
                namespace=_TRUST_NAMESPACE,
            )
            if item is None:
                return []

            raw = item.value
            if isinstance(raw, list):
                return [AgentOutcome(**o) if isinstance(o, dict) else o for o in raw]
            return []
        except Exception as e:
            logger.warning("加载 Agent 信任度记录失败: agent=%s, err=%s", agent_name, e)
            return []

    @staticmethod
    def _compute_metrics(outcomes: list[AgentOutcome]) -> AgentTrustMetrics:
        """从 Agent 的所有历史记录计算累积信任度指标

        Args:
            outcomes: 该 Agent 的所有历史记录

        Returns:
            累积信任度指标
        """
        if not outcomes:
            return AgentTrustMetrics()

        n = len(outcomes)
        correct_count = sum(1 for o in outcomes if o.is_correct)
        win_rate = correct_count / n if n > 0 else 0.0

        # ── 各方向准确率 ──
        bullish_outcomes = [o for o in outcomes if o.predicted_direction == "Bullish"]
        bearish_outcomes = [o for o in outcomes if o.predicted_direction == "Bearish"]
        neutral_outcomes = [o for o in outcomes if o.predicted_direction == "Neutral"]

        bullish_win = (
            sum(1 for o in bullish_outcomes if o.is_correct) / len(bullish_outcomes)
            if bullish_outcomes
            else 0.0
        )
        bearish_win = (
            sum(1 for o in bearish_outcomes if o.is_correct) / len(bearish_outcomes)
            if bearish_outcomes
            else 0.0
        )
        neutral_win = (
            sum(1 for o in neutral_outcomes if o.is_correct) / len(neutral_outcomes)
            if neutral_outcomes
            else 0.0
        )

        sector_groups: dict[str, list[AgentOutcome]] = {}
        for outcome in outcomes:
            if outcome.sector:
                sector_groups.setdefault(outcome.sector, []).append(outcome)

        sector_win_rates: dict[str, float] = {}
        sector_sample_counts: dict[str, int] = {}
        for sector, sector_outcomes in sector_groups.items():
            sector_sample_counts[sector] = len(sector_outcomes)
            sector_correct = sum(1 for o in sector_outcomes if o.is_correct)
            sector_win_rates[sector] = round(sector_correct / len(sector_outcomes), 3)

        # ── Brier score（置信度校准）──
        # Brier = 1/N Σ (confidence - correctness)^2
        # correctness = 1 if correct else 0
        brier_sum = 0.0
        for o in outcomes:
            correctness = 1.0 if o.is_correct else 0.0
            brier_sum += (o.predicted_confidence - correctness) ** 2
        brier_score = brier_sum / n if n > 0 else 0.0

        # ── 置信度偏差（正 = 过度自信）──
        confidence_bias = statistics.mean(
            [o.predicted_confidence - (1.0 if o.is_correct else 0.0) for o in outcomes]
        )

        # ── 校准曲线 ──
        calibration_curve = _build_calibration_curve(outcomes)

        # ── 评分偏差 ──
        # 使用价格变动绝对值的归一化作为"评分错误"的代理
        # 如果是 Bullish 但 price 跌了，score 应该低
        # 简单的代理：score 偏差不直接可测；用方向准确率反映
        # 实际评分偏差：预测评分 vs "理想评分"
        # 理想评分：方向正确时 ≈ 平均值偏上，方向错误时 ≈ 平均值偏下
        # 更简单的代理：score vs 60（中性基准线）
        # 如果 agent 总是打高分（>70）但方向准确率低 → 乐观偏差
        score_errors: list[float] = []
        for o in outcomes:
            # 将实际价格变动归一化到 [-1, 1]，映射到评分范围
            # 价格变动 +-10% 视为极端
            normalized_return = max(-1.0, min(1.0, o.actual_price_change_pct / 10.0))
            # 方向正确时理想评分 = 50 + 50 * normalized_return * direction_sign
            # 方向错误时理想评分 = 50 - 50 * normalized_return * direction_sign
            direction_sign = (
                1
                if o.predicted_direction == "Bullish"
                else -1
                if o.predicted_direction == "Bearish"
                else 0
            )
            if direction_sign != 0:
                # 如果方向是 Bullish，当价格涨时理想评分高
                # 如果方向是 Bearish，当价格跌时理想评分高
                ideal_score = 50 + 50 * normalized_return * direction_sign
            else:
                # Neutral: 理想评分 = 50（中性）
                ideal_score = 50.0
            ideal_score = max(0.0, min(100.0, ideal_score))
            score_errors.append(o.predicted_score - ideal_score)

        avg_score_error = statistics.mean([abs(e) for e in score_errors]) if score_errors else 0.0
        optimism_bias = statistics.mean(score_errors) if score_errors else 0.0

        # ── 趋势（最近 vs 较早的 win_rate）──
        recent_window = min(_RECENT_WINDOW, n)
        recent_outcomes = outcomes[-recent_window:]
        recent_correct = sum(1 for o in recent_outcomes if o.is_correct)
        recent_win_rate = recent_correct / recent_window if recent_window > 0 else 0.0

        # 趋势方向：如果最近 vs 总体差异 >= 0.1 且样本足够
        trend = "stable"
        if n >= _RECENT_WINDOW * 2:
            diff = recent_win_rate - win_rate
            if diff > 0.1:
                trend = "improving"
            elif diff < -0.1:
                trend = "declining"

        return AgentTrustMetrics(
            total_samples=n,
            win_rate=round(win_rate, 3),
            bullish_win_rate=round(bullish_win, 3),
            bearish_win_rate=round(bearish_win, 3),
            neutral_win_rate=round(neutral_win, 3),
            sector_win_rates=sector_win_rates,
            sector_sample_counts=sector_sample_counts,
            brier_score=round(brier_score, 4),
            confidence_bias=round(confidence_bias, 4),
            calibration_curve=calibration_curve,
            avg_score_error=round(avg_score_error, 2),
            optimism_bias=round(optimism_bias, 2),
            recent_win_rate=round(recent_win_rate, 3),
            trend_direction=trend,
            recent_count=recent_window,
        )

    @staticmethod
    def _generate_summary(
        agent_name: str,
        metrics: AgentTrustMetrics,
    ) -> str:
        """生成信任度画像的一句话摘要

        Args:
            agent_name: Agent 名称
            metrics: 累积信任度指标

        Returns:
            中文可读的一句话摘要
        """
        name = agent_name.replace("master.", "").replace("analyst.", "")
        if not metrics.total_samples:
            return f"{name}：暂无足够数据评估信任度"

        parts: list[str] = []

        # 准确率
        win_pct = round(metrics.win_rate * 100)
        if win_pct >= 70:
            parts.append(f"方向准确率 {win_pct}%（高）")
        elif win_pct >= 50:
            parts.append(f"方向准确率 {win_pct}%（中）")
        else:
            parts.append(f"方向准确率 {win_pct}%（低）")

        # 校准
        if metrics.brier_score < 0.1:
            parts.append("置信度校准良好")
        elif metrics.brier_score < 0.2:
            parts.append("置信度校准一般")
        else:
            parts.append("置信度校准较差")

        # 偏差
        if metrics.optimism_bias > 5:
            parts.append(f"偏乐观（评分常高估 {metrics.optimism_bias:.0f} 分）")
        elif metrics.optimism_bias < -5:
            parts.append(f"偏保守（评分常低估 {abs(metrics.optimism_bias):.0f} 分）")

        # 趋势
        if metrics.trend_direction == "improving":
            parts.append("近期准确率呈上升趋势")
        elif metrics.trend_direction == "declining":
            parts.append("⚠ 近期准确率呈下降趋势")

        parts.append(f"样本量 {metrics.total_samples}")
        return f"{name}：{'，'.join(parts)}。"


# ── 辅助函数 ──────────────────────────────────────────────────


def _build_calibration_curve(
    outcomes: list[AgentOutcome],
    buckets: int = _CALIBRATION_BUCKETS,
) -> list[dict[str, float]]:
    """构建置信度校准曲线

    将置信度 [0,1] 等分为 N 个 bucket，计算每个 bucket 内的实际准确率。
    理想情况下，bucket 内准确率 ≈ bucket 的置信度中点。

    回归测试关键性质：
    - 每个 bucket 的 count >= 0
    - 所有 bucket 的 count 之和 = n
    - bucket 中点单调递增

    Args:
        outcomes: Agent 的所有历史记录
        buckets: 分桶数量（默认 10，每 10 个百分点一级）

    Returns:
        校准数据点列表：
        [{"bucket": 0.05, "acc": 0.5, "count": 10}, ...]
        空列表表示样本不足（< buckets）
    """
    if len(outcomes) < buckets:
        return []

    # 分桶
    bucket_data: list[list[float]] = [[] for _ in range(buckets)]

    for o in outcomes:
        conf = o.predicted_confidence
        correct = 1.0 if o.is_correct else 0.0
        bucket_idx = min(int(conf * buckets), buckets - 1)
        bucket_data[bucket_idx].append(correct)

    curve: list[dict[str, float]] = []
    for i, items in enumerate(bucket_data):
        if not items:
            continue
        bucket_mid = (i + 0.5) / buckets
        acc = sum(items) / len(items)
        curve.append({
            "bucket": round(bucket_mid, 2),
            "acc": round(acc, 3),
            "count": len(items),
        })

    return curve


def _outcome_dedupe_key(outcome: AgentOutcome) -> str:
    return (
        f"{outcome.session_id}_{outcome.stock_code}_"
        f"{outcome.sector}_{outcome.predicted_direction}"
    )


def compute_weight_factor(metrics: AgentTrustMetrics, sector: str = "") -> float:
    """根据信任度指标计算投票权重因子

    供 aggregate 节点使用（M4 动态权重的前置函数）。
    权重因子范围 0.5-1.5，中心值 1.0 = 无调整。

    公式：
      base = win_rate * 0.6 + (1 - brier_score) * 0.2 + confidence_bias_penalty * 0.2
      factor = 0.5 + base

    Args:
        metrics: Agent 的信任度指标
        sector: 可选板块标识；有足够板块样本时使用该板块胜率

    Returns:
        权重因子（数据不足时返回 1.0）
    """
    if metrics.total_samples < _MIN_RELIABLE_SAMPLES:
        return 1.0

    win_rate = metrics.win_rate
    if (
        sector
        and metrics.sector_sample_counts.get(sector, 0) >= _MIN_RELIABLE_SAMPLES
        and sector in metrics.sector_win_rates
    ):
        win_rate = metrics.sector_win_rates[sector]

    # 准确率贡献（0-0.6）
    win_component = win_rate * 0.6

    # 校准贡献（0-0.2）：Brier 越小越好；1 - brier 归一化
    calibration_component = max(0, 1.0 - metrics.brier_score * 2) * 0.2

    # 置信度偏差惩罚
    bias_penalty = max(0, 1.0 - abs(metrics.confidence_bias) * 2) * 0.2

    base = win_component + calibration_component + bias_penalty
    factor = 0.5 + base

    return round(max(0.5, min(1.5, factor)), 2)


__all__ = [
    "AgentOutcome",
    "AgentTrustMetrics",
    "TrustTracker",
    "TrustReport",
    "compute_weight_factor",
]
