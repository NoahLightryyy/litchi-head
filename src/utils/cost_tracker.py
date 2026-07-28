"""LLM 调用费用跟踪"""

import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from pydantic import BaseModel, Field


class SessionCostSummary(BaseModel):
    """Aggregated token usage and CNY cost for one LLM session."""

    session_id: str
    call_count: int = 0
    prompt_tokens: int = 0
    prompt_cache_hit_tokens: int = 0
    prompt_cache_miss_tokens: int = 0
    completion_tokens: int = 0
    cost_yuan: float = 0.0
    models: set[str] = Field(default_factory=set)


class CostTracker:
    """跟踪 LLM 调用费用，支持按 session 和按日汇总"""

    PRICES = {
        # 2026-07-28 官方人民币价格，单位：元 / 1M tokens。
        # deepseek-chat / reasoner 兼容映射到 V4 Flash。
        "deepseek-chat": {"cache_hit": 0.02, "cache_miss": 1.0, "output": 2.0},
        "deepseek-reasoner": {
            "cache_hit": 0.02,
            "cache_miss": 1.0,
            "output": 2.0,
        },
        "deepseek-v4-flash": {
            "cache_hit": 0.02,
            "cache_miss": 1.0,
            "output": 2.0,
        },
        "deepseek-v4-pro": {
            "cache_hit": 0.025,
            "cache_miss": 3.0,
            "output": 6.0,
        },
    }
    _FALLBACK_PRICES = {"cache_hit": 0.02, "cache_miss": 1.0, "output": 2.0}

    def __init__(self, log_dir: str = "data/cost_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._records: list = []

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        agent: str,
        session_id: str = "",
        prompt_cache_hit_tokens: int = 0,
        prompt_cache_miss_tokens: int | None = None,
    ) -> None:
        """记录一次 LLM 调用"""
        prices = self.PRICES.get(model, self._FALLBACK_PRICES)
        cache_hit = max(prompt_cache_hit_tokens, 0)
        cache_miss = (
            max(prompt_tokens - cache_hit, 0)
            if prompt_cache_miss_tokens is None
            else max(prompt_cache_miss_tokens, 0)
        )
        cost = (
            cache_hit * prices["cache_hit"]
            + cache_miss * prices["cache_miss"]
            + completion_tokens * prices["output"]
        ) / 1_000_000

        self._records.append({
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "agent": agent,
            "session_id": session_id,
            "prompt_tokens": prompt_tokens,
            "prompt_cache_hit_tokens": cache_hit,
            "prompt_cache_miss_tokens": cache_miss,
            "completion_tokens": completion_tokens,
            "cost_yuan": round(cost, 6),
        })

    def session_cost(self, session_id: str) -> float:
        return round(sum(r["cost_yuan"] for r in self._records if r["session_id"] == session_id), 4)

    def session_summary(self, session_id: str) -> SessionCostSummary:
        """Aggregate all in-memory records for one debate session."""
        records = [r for r in self._records if r["session_id"] == session_id]
        return SessionCostSummary(
            session_id=session_id,
            call_count=len(records),
            prompt_tokens=sum(int(r["prompt_tokens"]) for r in records),
            prompt_cache_hit_tokens=sum(
                int(r.get("prompt_cache_hit_tokens", 0)) for r in records
            ),
            prompt_cache_miss_tokens=sum(
                int(r.get("prompt_cache_miss_tokens", r["prompt_tokens"]))
                for r in records
            ),
            completion_tokens=sum(int(r["completion_tokens"]) for r in records),
            cost_yuan=round(sum(float(r["cost_yuan"]) for r in records), 6),
            models={str(r["model"]) for r in records},
        )

    def daily_report(self) -> str:
        """生成今日费用报告"""
        today = date.today().isoformat()
        today_records = [r for r in self._records if r["timestamp"].startswith(today)]
        if not today_records:
            return "📊 今日暂无 LLM 调用"

        total = sum(r["cost_yuan"] for r in today_records)
        by_model = defaultdict(float)
        for r in today_records:
            by_model[r["model"]] += r["cost_yuan"]

        lines = [f"📊 今日 LLM 费用 ({today})", f"总费用: ¥{total:.4f}", ""]
        for model, cost in sorted(by_model.items(), key=lambda x: -x[1]):
            lines.append(f"  {model}: ¥{cost:.4f}")
        return "\n".join(lines)

    def save(self):
        """保存记录到文件"""
        if not self._records:
            return
        path = self.log_dir / f"{date.today().isoformat()}.jsonl"
        with open(path, "a", encoding="utf-8") as f:
            for r in self._records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        self._records.clear()


cost_tracker = CostTracker()


__all__ = ["CostTracker", "SessionCostSummary", "cost_tracker"]
