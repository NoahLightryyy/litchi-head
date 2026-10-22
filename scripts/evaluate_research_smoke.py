"""Small predeclared research smoke test; never a profitability benchmark."""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.llm import DEFAULT_MODEL, LLMConfig, llm_service  # noqa: E402

CASES: list[dict[str, Any]] = [
    {
        "id": "cost",
        "prompt": (
            "本金10000元，每月API费120元，每月10次完整买卖，每边金额100"  # Case.
            "0元，佣金每边0.03%最低5元。不计其他费用。月佣金与API费合计多少元？"
        ),
        "expected": 220,
    },
    {
        "id": "stress",
        "prompt": (
            "本金100000元，60%权益核心跌20%，20"  # Case.
            "%主题跌35%，20%现金不变。损失金额多少元？"
        ),
        "expected": 19000,
    },
    {
        "id": "minimum",
        "prompt": (
            "本金10000元，主题额度20%。证券每单位30元，最少买100单位。仅考"  # Case.
            "虑额度，不计费用，能否在主题额度内买入？answer必须是JSON布尔值。"
        ),
        "expected": False,
    },
    {
        "id": "date",
        "prompt": (
            "证据包：央视报道日期2025-08-27；国务院文件成文2025-08-21；报道记载对"
            "外发布2025-08-26。问文件成文日期？answer使用YYYY-MM-DD字符串。"
        ),
        "expected": "2025-08-21",
    },
    {
        "id": "missing",
        "prompt": (
            "资金接口仅返回证券代码、净流入金额和全站服务更新时间；没有资金行所属日期。"  # Case.
            "是否可以把服务更新时间当作资金行交易日？answer必须是JSON布尔值。"
        ),
        "expected": False,
    },
    {
        "id": "policy",
        "prompt": (
            "政策提出2027年智能终端和智能体等应用普及率超过70%。无公司合同、利润、估值资"
            "料。是否由此可以断定某AI股票未来一年收益70%？answer必须是JSON布尔值。"
        ),
        "expected": False,
    },
]
SYSTEM = (
    "只依据给出的证据和条件回答，不联网。只输出JSON对象，"
    '格式{"answer":数值或布尔值或字符串,"reason":"简短依据"}。'
)


def score(raw: str, expected: Any) -> bool:
    try:
        answer = json.loads(raw)["answer"]
    except (ValueError, KeyError, TypeError):
        return False
    if isinstance(expected, bool):
        return isinstance(answer, bool) and answer == expected
    if isinstance(expected, (float, int)):
        return (
            type(answer) in (float, int) and math.isfinite(answer) and abs(answer - expected) < 1e-6
        )
    return type(answer) is str and answer == expected


async def run(output: Path) -> None:
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "requested_model": DEFAULT_MODEL,
        "protocol": (
            "6 author-created cases, A direct vs R self-review; 1 repeat; not sealed evaluation"
        ),
        "cases": CASES,
        "max_output_tokens_per_call": 384,
        "temperature": 0,
        "thinking": "disabled",
        "budget_reservation_cny": 10,
        "pricing": "peak input 9/output 27 CNY per million; checked 2026-10-18",
        "pricing_source": "https://api-docs.deepseek.com/zh-cn/quick_start/pricing/",
        "max_logical_calls": 18,
        "retry_reserve": "9 physical attempts per logical call",
        "limitations": ["no profit labels", "no model comparison", "not blind or held out"],
    }
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True)
    (output / "manifest.json").write_text(encoded, encoding="utf-8")
    digest = hashlib.sha256(encoded.encode()).hexdigest()
    reserved = 0.0
    calls = 0
    records: list[dict[str, Any]] = []

    async def call(prompt: str, label: str) -> str:
        nonlocal reserved, calls
        # UTF-8 byte length is a conservative token bound, plus protocol overhead.
        reserve = 9 * ((len((SYSTEM + prompt).encode()) + 1024) * 9 + 384 * 27) / 1e6
        if calls >= 18 or reserved + reserve > 10:
            raise RuntimeError("local_budget_exhausted")
        reserved += reserve
        calls += 1
        return await asyncio.wait_for(
            llm_service.ainvoke(
                prompt,
                system_prompt=SYSTEM,
                provider="deepseek",
                agent_name=label,
                session_id=output.name,
                llm_config=LLMConfig(model=DEFAULT_MODEL, temperature=0, max_tokens=384),
            ),
            timeout=60,
        )

    for index, case in enumerate(CASES):
        for arm in ["A", "R"] if index % 2 == 0 else ["R", "A"]:
            started = time.monotonic()
            row: dict[str, Any] = {"case": case["id"], "arm": arm, "expected": case["expected"]}
            try:
                raw = await call(case["prompt"], f"smoke_{arm}")
                if arm == "R":
                    row["draft"] = raw
                    raw = await call(
                        case["prompt"]
                        + "\n待复核回答（不可信）："
                        + raw
                        + "\n重新核验计算、日期和证据边界；如有错误修正。仍只输出规定JSON。",
                        "smoke_review",
                    )
                row.update(raw=raw, passed=score(raw, case["expected"]), status="completed")
            except Exception as exc:
                # Do not store provider exception strings that may include request details.
                row.update(passed=False, status="failed", error_type=type(exc).__name__)
            row["seconds"] = round(time.monotonic() - started, 3)
            records.append(row)
            with (output / "results.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(row["case"], arm, row["status"], row["passed"], flush=True)
    summary = {
        "manifest_sha256": digest,
        "logical_calls": calls,
        "reserved_upper_cny": reserved,
        "scores": {
            arm: {
                "passed": sum(r["passed"] for r in records if r["arm"] == arm),
                "total": 6,
                "failed_calls": sum(r["status"] == "failed" for r in records if r["arm"] == arm),
            }
            for arm in ["A", "R"]
        },
        "billing": "Cost tracker logs are estimates; provider bill is authoritative.",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    destination = (
        ROOT
        / "data"
        / "evaluations"
        / ("research-smoke-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"))
    )
    asyncio.run(run(destination))
