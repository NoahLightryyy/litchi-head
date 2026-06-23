"""LLM 调用费用跟踪"""

import json
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path


class CostTracker:
    """跟踪 LLM 调用费用，支持按 session 和按日汇总"""

    PRICES = {
        "deepseek-chat": {"input": 0.5, "output": 1.0},
    }

    def __init__(self, log_dir: str = "data/cost_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._records: list = []

    def record(self, model: str, prompt_tokens: int, completion_tokens: int,
               agent: str, session_id: str = ""):
        """记录一次 LLM 调用"""
        prices = self.PRICES.get(model, {"input": 0.5, "output": 1.0})
        cost = (prompt_tokens * prices["input"] + completion_tokens * prices["output"]) / 1_000_000

        self._records.append({
            "timestamp": datetime.now().isoformat(),
            "model": model,
            "agent": agent,
            "session_id": session_id,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost_yuan": round(cost, 6),
        })

    def session_cost(self, session_id: str) -> float:
        return round(sum(r["cost_yuan"] for r in self._records if r["session_id"] == session_id), 4)

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
