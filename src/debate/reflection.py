"""M2 交易后反思模块

反思闭环 —— 对比历史决策预测 vs 实际市场表现，生成结构化反思，
记录教训并注入到未来的分析决策中。

核心流程：
  A. 反思生成（post-hoc）：给定 DebateResult + ActualOutcome → LLM 生成 ReflectionRecord
  B. 反思注入（during debate）：查询 ("reflective", "debate") 命名空间 → 注入 prompt

用法：
    from src.debate.reflection import generate_reflection, _format_reflection_context

    # 反思生成
    reflection = await generate_reflection(decision=result, outcome=outcome)

    # 反思注入（编排器中自动调用）
    context = _format_reflection_context(reflection_items, "000001")
"""

from __future__ import annotations

import time
from typing import cast

from pydantic import BaseModel, Field

from src.memory.store import MemoryItem, MemoryStore

# ── 数据模型 ──────────────────────────────────────────────────


class ActualOutcome(BaseModel):
    """实际市场结果输入

    由外部提供（或回测引擎生成），用于与历史决策中的预测进行对比。
    这是 M2 反思闭环的触发条件——没有实际结果就无法反思。

    Attributes:
        stock_code: 股票代码
        decision_date: 原始决策日期（ISO 格式字符串）
        evaluation_date: 评估日期（何时获取实际结果）
        price_change_pct: 持有期间价格变动百分比（如 +5.2 表示涨了 5.2%）
        actual_direction: 实际方向（Bullish/Bearish/Neutral）
        holding_period_days: 持有天数（决策日到评估日）
        notes: 补充说明（如期间重大事件）
    """

    stock_code: str
    decision_date: str = ""
    evaluation_date: str = ""
    price_change_pct: float = 0.0
    actual_direction: str = "Neutral"
    holding_period_days: int = 0
    notes: str = ""


class ReflectionRecord(BaseModel):
    """反思记录 —— LLM 对比预测 vs 实际市场表现后生成的结构化反思

    包含原始预测、实际结果、反思文本、关键教训和改进建议。
    存储在 ("reflective", "debate") 命名空间中，供未来分析注入使用。

    Attributes:
        session_id: 被反思的原始辩论会话标识
        stock_code: 股票代码
        stock_name: 股票名称
        decision_date: 原始决策日期
        evaluation_date: 评估日期
        predicted_direction: 预测的方向（Bullish/Bearish/Neutral）
        predicted_consensus: 预测时的共识评级
        predicted_action: 预测的操作建议（buy/sell/hold）
        predicted_score: 预测的评分（1-100）
        predicted_confidence: 预测的置信度（0.0-1.0）
        actual_direction: 实际市场方向
        actual_price_change_pct: 实际价格变动百分比
        was_correct: 方向判断是否正确
        accuracy_score: 综合准确率评分（0.0-1.0）
        reflection_text: LLM 生成的完整反思文本
        key_lessons: 关键教训列表
        improvement_suggestions: 改进建议列表
        identified_biases: 识别的决策偏向（如过度乐观/锚定效应等）
        latency_ms: 反思生成耗时（毫秒）
    """

    session_id: str
    stock_code: str
    stock_name: str = ""
    decision_date: str = ""
    evaluation_date: str = ""
    # 预测
    predicted_direction: str = "Neutral"
    predicted_consensus: str = ""
    predicted_action: str = "hold"
    predicted_score: float = 0.0
    predicted_confidence: float = 0.0
    # 实际
    actual_direction: str = "Neutral"
    actual_price_change_pct: float = 0.0
    # 反思
    was_correct: bool = False
    accuracy_score: float = 0.0
    reflection_text: str = ""
    key_lessons: list[str] = Field(default_factory=list)
    improvement_suggestions: list[str] = Field(default_factory=list)
    identified_biases: list[str] = Field(default_factory=list)
    latency_ms: float = 0.0


# ── 核心函数 ──────────────────────────────────────────────────


async def generate_reflection(
    decision_summary: dict,
    outcome: ActualOutcome,
    session_id: str = "",
) -> ReflectionRecord:
    """调用 LLM 对比历史决策预测与实际市场结果，生成结构化反思

    这是 M2 反思闭环的核心——LLM 以反思分析师的角色阅读决策记录和实际结果，
    识别判断中的偏差、漏掉的风险信号和可以改进的地方。

    Args:
        decision_summary: 历史决策摘要（来自 DebateResult.to_summary_dict()）
        outcome: 实际市场结果
        session_id: 被反思的原始会话标识

    Returns:
        结构化反思记录（LLM 调用失败时返回默认空记录）
    """
    start = time.monotonic()

    # 构建反思 prompt
    prompt = (
        "你是一位投资反思分析师。你的任务是对比以下投资决策的预测与实际市场结果，"
        "找出判断中的得失、偏差和改进机会。\n\n"
        "--- 原始决策 ---\n"
    )
    for key, val in decision_summary.items():
        prompt += f"  {key}：{val}\n"

    prompt += (
        f"\n--- 实际市场结果 ---\n"
        f"  方向：{outcome.actual_direction}\n"
        f"  价格变动：{outcome.price_change_pct:+.2f}%\n"
        f"  持有天数：{outcome.holding_period_days}\n"
        f"  决策日期：{outcome.decision_date}\n"
        f"  评估日期：{outcome.evaluation_date}\n"
    )
    if outcome.notes:
        prompt += f"  备注：{outcome.notes}\n"

    prompt += (
        "\n请从以下维度进行反思分析：\n"
        "1. was_correct: 方向判断是否正确？（true/false）\n"
        "2. accuracy_score: 综合准确率评分（0.0=完全错误，1.0=完全正确）\n"
        "3. reflection_text: 完整反思文本——哪些判断是对的？哪些错了？为什么？\n"
        "4. key_lessons: 2-4 条关键教训（具体、可执行）\n"
        "5. improvement_suggestions: 2-3 条改进建议（下次分析应该注意什么）\n"
        "6. identified_biases: 发现的决策偏向（如过度乐观、锚定效应、从众效应等）\n"
    )

    system_prompt = (
        "你是一位冷静、诚实的投资反思分析师。你的任务不是批评决策者，"
        "而是从每次决策中提取可复用的经验教训。"
        "请用中文输出所有文本字段。"
        "对方向判断的正确性评估要客观——看涨但实际跌了就是不对，不要找借口。"
    )

    try:
        from src.utils.llm import llm_service as _ls
        raw = cast(ReflectionRecord, await _ls.invoke_structured(
            prompt=prompt,
            output_model=ReflectionRecord,
            system_prompt=system_prompt,
            agent_name="reflection_analyst",
            session_id=session_id,
        ))
        elapsed = (time.monotonic() - start) * 1000

        return ReflectionRecord(
            session_id=session_id,
            stock_code=outcome.stock_code,
            stock_name=decision_summary.get("股票名称", ""),
            decision_date=outcome.decision_date,
            evaluation_date=outcome.evaluation_date,
            predicted_direction=decision_summary.get("方向分布", {}).get("consensus", "Neutral"),
            predicted_consensus=str(decision_summary.get("共识", "")),
            predicted_action=str(decision_summary.get("最终建议", "hold")).lower(),
            predicted_score=float(decision_summary.get("平均评分", 0)),
            predicted_confidence=float(decision_summary.get("置信度", 0)),
            actual_direction=outcome.actual_direction,
            actual_price_change_pct=outcome.price_change_pct,
            was_correct=raw.was_correct,
            accuracy_score=raw.accuracy_score,
            reflection_text=raw.reflection_text,
            key_lessons=list(raw.key_lessons),
            improvement_suggestions=list(raw.improvement_suggestions),
            identified_biases=list(raw.identified_biases),
            latency_ms=round(elapsed, 0),
        )

    except Exception:
        elapsed = (time.monotonic() - start) * 1000
        return ReflectionRecord(
            session_id=session_id,
            stock_code=outcome.stock_code,
            decision_date=outcome.decision_date,
            evaluation_date=outcome.evaluation_date,
            actual_direction=outcome.actual_direction,
            actual_price_change_pct=outcome.price_change_pct,
            reflection_text="反思生成失败（LLM 调用异常）",
            latency_ms=round(elapsed, 0),
        )


def _format_reflection_context(
    items: list[MemoryItem],
    stock_code: str,
) -> str:
    """将反思记忆格式化为 prompt 插入文本

    从 MemoryStore 查询到的反思条目格式化成可读的上下文，
    注入到策略师 prompt 中，帮助本轮决策从历史错误中学习。

    Args:
        items: 反思 MemoryItem 列表（来自 ("reflective", "debate") 命名空间）
        stock_code: 当前股票代码（过滤出相关反思）

    Returns:
        格式化后的反思上下文文本（无相关记录时返回 ""）
    """
    if not items:
        return ""

    # 过滤与当前股票相关的反思，取最近的 3 条
    relevant: list[dict] = []
    for item in items:
        val = item.value if isinstance(item.value, dict) else {}
        if val.get("stock_code") == stock_code:
            relevant.append(val)

    if not relevant:
        return ""

    lines = ["", "🧠 历史反思记录（从过去的错误中学习）：", "━━━━━━━━━━━━━━━━━━━━━━━━━━"]
    lines.append("以下是本系统对该股票历史决策的事后反思——包括判断得失和关键教训。")
    lines.append("请在分析时特别注意避免重蹈覆辙：")
    lines.append("")

    for i, reflection in enumerate(reversed(relevant[-3:]), 1):
        decision_date = str(reflection.get("decision_date", "未知日期"))[:10]
        eval_date = str(reflection.get("evaluation_date", "未知日期"))[:10]
        lines.append(f"──── 反思 #{i}（决策日：{decision_date}，评估日：{eval_date}）────")

        # 预测 vs 实际
        pred_dir = reflection.get("predicted_direction", "N/A")
        actual_dir = reflection.get("actual_direction", "N/A")
        actual_pct = reflection.get("actual_price_change_pct", 0)
        was_correct = reflection.get("was_correct", False)

        correct_mark = "✅" if was_correct else "❌"
        lines.append(
            f"  方向判断：预测 {pred_dir} vs 实际 {actual_dir}"
            f"（{actual_pct:+.1f}%）{correct_mark}"
        )

        pred_score = reflection.get("predicted_score", "N/A")
        pred_confidence = reflection.get("predicted_confidence", "N/A")
        lines.append(f"  原始评分：{pred_score} | 置信度：{pred_confidence}")

        accuracy = reflection.get("accuracy_score", "N/A")
        if isinstance(accuracy, (int, float)):
            lines.append(f"  准确率：{accuracy:.1%}")

        # 反思核心内容
        reflection_text = reflection.get("reflection_text", "")
        if reflection_text:
            # 截取前 300 字作为提示
            snippet = reflection_text[:300]
            if len(reflection_text) > 300:
                snippet += "..."
            lines.append(f"  反思：{snippet}")

        # 关键教训
        lessons = reflection.get("key_lessons", [])
        if lessons:
            lines.append("  📌 关键教训：")
            for lesson in lessons:
                lines.append(f"    ⚡ {lesson}")

        # 改进建议
        suggestions = reflection.get("improvement_suggestions", [])
        if suggestions:
            lines.append("  💡 改进建议：")
            for s in suggestions:
                lines.append(f"    → {s}")

        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━")
    return "\n".join(lines)


async def _load_decision_from_memory(
    store: MemoryStore,
    stock_code: str,
) -> dict | None:
    """从 episodic 记忆加载该股票的最新决策记录

    用于反思生成时——从存储的决策中提取原始预测数据，
    与 ActualOutcome 对比生成 ReflectionRecord。

    Args:
        store: 记忆存储实例
        stock_code: 股票代码（用作 key）

    Returns:
        决策记录 dict（不存在时返回 None）
    """
    try:
        item = await store.get(
            key=stock_code,
            namespace=("episodic", "debate"),
        )
        if item is None:
            return None
        if isinstance(item.value, dict):
            return item.value
        return None
    except Exception:
        return None


__all__ = [
    "ActualOutcome",
    "ReflectionRecord",
    "generate_reflection",
    "_format_reflection_context",
    "_load_decision_from_memory",
]
