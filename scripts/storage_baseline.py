#!/usr/bin/env python
"""可重复的本地存储容量基线。

本工具只使用合成的 Agent 决策记录，不读取或改写真实业务数据。它比较：

1. JSONL 追加 + 全文件查询（当前 episodic/reflective 记忆模式）
2. JSON 对象逐条覆写（当前 RetroStore 模式）
3. SQLite WAL + 主键索引（候选 SQL 基线）

结果只代表执行机器和给定参数，不能替代生产压测。
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from pydantic import BaseModel, Field


class BenchmarkConfig(BaseModel):
    """一次容量基线的输入口径。"""

    record_count: int = Field(default=1_000, gt=0)
    payload_bytes: int = Field(default=4_096, gt=0)
    lookup_count: int = Field(default=100, gt=0)
    sqlite_batch_size: int = Field(default=100, gt=0)


class EnvironmentInfo(BaseModel):
    """影响基准可比性的本机环境。"""

    python_version: str
    platform: str
    processor: str
    cpu_count: int | None


class BenchmarkResult(BaseModel):
    """单个后端的测量结果。"""

    backend: str
    records_written: int
    records_read: int
    write_seconds: float
    write_ops_per_second: float
    lookup_p50_ms: float
    lookup_p95_ms: float
    storage_bytes: int
    bytes_per_record: float
    errors: list[str] = Field(default_factory=list)


class CapacityReport(BaseModel):
    """完整的基准报告。"""

    generated_at: datetime
    config: BenchmarkConfig
    environment: EnvironmentInfo
    results: list[BenchmarkResult]
    disclaimer: str = "仅代表本机合成基线，不是生产容量承诺。"


def build_decision_record(index: int, payload_bytes: int) -> dict[str, Any]:
    """生成可重复、带审计字段的合成 Agent 决策记录。"""
    stock_code = f"{index % 1_000_000:06d}"
    record: dict[str, Any] = {
        "session_id": f"bench-{index:08d}",
        "stock_code": stock_code,
        "decision_date": "2026-07-28",
        "schema_version": 1,
        "source": "synthetic-capacity-baseline",
        "consensus": "Neutral",
        "confidence": 0.625,
        "agent_analyses": [
            {
                "agent_name": "master.baseline",
                "direction": "Neutral",
                "confidence": 0.625,
                "summary": "",
            }
        ],
    }
    encoded_size = len(json.dumps(record, ensure_ascii=False).encode("utf-8"))
    record["agent_analyses"][0]["summary"] = "基" * max(
        1,
        (payload_bytes - encoded_size + 2) // 3,
    )
    while len(json.dumps(record, ensure_ascii=False).encode("utf-8")) < payload_bytes:
        record["agent_analyses"][0]["summary"] += "x"
    return record


def _percentile_ms(samples: list[float], percentile: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * percentile)))
    return round(ordered[index] * 1_000, 4)


def _storage_bytes(path: Path) -> int:
    if path.is_file():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _result(
    *,
    backend: str,
    config: BenchmarkConfig,
    records_read: int,
    write_seconds: float,
    lookup_samples: list[float],
    storage_bytes: int,
    errors: list[str],
) -> BenchmarkResult:
    return BenchmarkResult(
        backend=backend,
        records_written=config.record_count,
        records_read=records_read,
        write_seconds=round(write_seconds, 6),
        write_ops_per_second=round(config.record_count / max(write_seconds, 1e-9), 2),
        lookup_p50_ms=_percentile_ms(lookup_samples, 0.50),
        lookup_p95_ms=_percentile_ms(lookup_samples, 0.95),
        storage_bytes=storage_bytes,
        bytes_per_record=round(storage_bytes / max(records_read, 1), 2),
        errors=errors,
    )


def benchmark_jsonl(base_path: Path, config: BenchmarkConfig) -> BenchmarkResult:
    """测量追加式 JSONL 与全文件查询。"""
    base_path.mkdir(parents=True, exist_ok=True)
    path = base_path / "decisions.jsonl"
    errors: list[str] = []

    started = time.perf_counter()
    with path.open("a", encoding="utf-8") as stream:
        for index in range(config.record_count):
            record = build_decision_record(index, config.payload_bytes)
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    write_seconds = time.perf_counter() - started

    def read_all() -> list[dict[str, Any]]:
        with path.open(encoding="utf-8") as stream:
            return [json.loads(line) for line in stream if line.strip()]

    records = read_all()
    lookup_samples: list[float] = []
    for index in range(config.lookup_count):
        target = f"bench-{index % config.record_count:08d}"
        lookup_started = time.perf_counter()
        matches = [
            record for record in read_all() if record.get("session_id") == target
        ]
        lookup_samples.append(time.perf_counter() - lookup_started)
        if len(matches) != 1:
            errors.append(f"session lookup mismatch: {target}")

    return _result(
        backend="jsonl",
        config=config,
        records_read=len(records),
        write_seconds=write_seconds,
        lookup_samples=lookup_samples,
        storage_bytes=_storage_bytes(base_path),
        errors=errors,
    )


def benchmark_json_object(base_path: Path, config: BenchmarkConfig) -> BenchmarkResult:
    """测量当前 RetroStore 风格的读全量、逐条覆写 JSON。"""
    base_path.mkdir(parents=True, exist_ok=True)
    path = base_path / "records.json"
    errors: list[str] = []

    started = time.perf_counter()
    for index in range(config.record_count):
        if path.exists():
            with path.open(encoding="utf-8") as stream:
                records = json.load(stream)
        else:
            records = {}
        record = build_decision_record(index, config.payload_bytes)
        records[record["session_id"]] = record
        with path.open("w", encoding="utf-8") as stream:
            json.dump(records, stream, ensure_ascii=False)
    write_seconds = time.perf_counter() - started

    with path.open(encoding="utf-8") as stream:
        records = json.load(stream)

    lookup_samples: list[float] = []
    for index in range(config.lookup_count):
        target = f"bench-{index % config.record_count:08d}"
        lookup_started = time.perf_counter()
        with path.open(encoding="utf-8") as stream:
            current = json.load(stream)
        found = current.get(target)
        lookup_samples.append(time.perf_counter() - lookup_started)
        if found is None:
            errors.append(f"session lookup missing: {target}")

    return _result(
        backend="json-object",
        config=config,
        records_read=len(records),
        write_seconds=write_seconds,
        lookup_samples=lookup_samples,
        storage_bytes=_storage_bytes(base_path),
        errors=errors,
    )


def benchmark_sqlite(base_path: Path, config: BenchmarkConfig) -> BenchmarkResult:
    """测量 SQLite WAL、批量事务和主键查询。"""
    base_path.mkdir(parents=True, exist_ok=True)
    path = base_path / "decisions.sqlite3"
    errors: list[str] = []
    connection = sqlite3.connect(path, timeout=5.0)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=FULL")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            session_id TEXT PRIMARY KEY,
            stock_code TEXT NOT NULL,
            decision_date TEXT NOT NULL,
            schema_version INTEGER NOT NULL,
            payload_json TEXT NOT NULL
        )
        """
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_decisions_stock_date "
        "ON decisions(stock_code, decision_date)"
    )

    started = time.perf_counter()
    batch: list[tuple[str, str, str, int, str]] = []
    for index in range(config.record_count):
        record = build_decision_record(index, config.payload_bytes)
        batch.append(
            (
                record["session_id"],
                record["stock_code"],
                record["decision_date"],
                record["schema_version"],
                json.dumps(record, ensure_ascii=False),
            )
        )
        if len(batch) >= config.sqlite_batch_size:
            with connection:
                connection.executemany(
                    """
                    INSERT INTO decisions (
                        session_id, stock_code, decision_date, schema_version, payload_json
                    ) VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(session_id) DO UPDATE SET
                        stock_code=excluded.stock_code,
                        decision_date=excluded.decision_date,
                        schema_version=excluded.schema_version,
                        payload_json=excluded.payload_json
                    """,
                    batch,
                )
            batch.clear()
    if batch:
        with connection:
            connection.executemany(
                """
                INSERT INTO decisions (
                    session_id, stock_code, decision_date, schema_version, payload_json
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET payload_json=excluded.payload_json
                """,
                batch,
            )
    write_seconds = time.perf_counter() - started

    records_read = int(connection.execute("SELECT COUNT(*) FROM decisions").fetchone()[0])
    lookup_samples: list[float] = []
    for index in range(config.lookup_count):
        target = f"bench-{index % config.record_count:08d}"
        lookup_started = time.perf_counter()
        found = connection.execute(
            "SELECT payload_json FROM decisions WHERE session_id = ?",
            (target,),
        ).fetchone()
        lookup_samples.append(time.perf_counter() - lookup_started)
        if found is None:
            errors.append(f"session lookup missing: {target}")

    connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    connection.close()
    return _result(
        backend="sqlite-wal",
        config=config,
        records_read=records_read,
        write_seconds=write_seconds,
        lookup_samples=lookup_samples,
        storage_bytes=_storage_bytes(base_path),
        errors=errors,
    )


def run_capacity_suite(base_path: Path, config: BenchmarkConfig) -> CapacityReport:
    """依次运行全部本地后端，避免磁盘竞争污染结果。"""
    runners: tuple[Callable[[Path, BenchmarkConfig], BenchmarkResult], ...] = (
        benchmark_jsonl,
        benchmark_json_object,
        benchmark_sqlite,
    )
    results = [
        runner(base_path / runner.__name__.removeprefix("benchmark_"), config)
        for runner in runners
    ]
    return CapacityReport(
        generated_at=datetime.now(UTC),
        config=config,
        environment=EnvironmentInfo(
            python_version=sys.version.split()[0],
            platform=platform.platform(),
            processor=platform.processor(),
            cpu_count=os.cpu_count(),
        ),
        results=results,
    )


def render_markdown(report: CapacityReport) -> str:
    """将机器可读结果渲染成便于评审的 Markdown。"""
    lines = [
        "# 存储容量合成基线",
        "",
        f"> {report.disclaimer}",
        "",
        f"- 记录数：{report.config.record_count}",
        f"- 单条目标载荷：{report.config.payload_bytes} bytes",
        f"- 随机查询次数：{report.config.lookup_count}",
        f"- Python：{report.environment.python_version}",
        "",
        "| 后端 | 写入 ops/s | 查询 p50 ms | 查询 p95 ms | 占用 bytes | 每条 bytes |",
        "|:--|--:|--:|--:|--:|--:|",
    ]
    for result in report.results:
        lines.append(
            f"| {result.backend} | {result.write_ops_per_second:.2f} | "
            f"{result.lookup_p50_ms:.4f} | {result.lookup_p95_ms:.4f} | "
            f"{result.storage_bytes} | {result.bytes_per_record:.2f} |"
        )
    lines.extend(
        [
            "",
            "## 解释边界",
            "",
            "- JSONL 模拟当前追加式记忆，但查询需要重新读取整个文件。",
            "- JSON Object 模拟当前复盘存储的逐条全文件覆写。",
            "- SQLite 使用 WAL、FULL 同步、批量事务和主键索引。",
            "- 结果不含网络、ORM、PostgreSQL、Redis、真实 LLM 或外部行情延迟。",
            "",
        ]
    )
    return "\n".join(lines)


def _write_report(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=int, default=1_000)
    parser.add_argument("--payload-bytes", type=int, default=4_096)
    parser.add_argument("--lookups", type=int, default=100)
    parser.add_argument("--sqlite-batch-size", type=int, default=100)
    parser.add_argument("--json-output", type=Path)
    parser.add_argument("--markdown-output", type=Path)
    args = parser.parse_args()

    config = BenchmarkConfig(
        record_count=args.records,
        payload_bytes=args.payload_bytes,
        lookup_count=args.lookups,
        sqlite_batch_size=args.sqlite_batch_size,
    )
    with tempfile.TemporaryDirectory(prefix="litchi-storage-baseline-") as tmp:
        report = run_capacity_suite(Path(tmp), config)

    json_content = report.model_dump_json(indent=2)
    markdown_content = render_markdown(report)
    if args.json_output:
        _write_report(args.json_output, json_content + "\n")
    if args.markdown_output:
        _write_report(args.markdown_output, markdown_content)
    if not args.json_output and not args.markdown_output:
        print(markdown_content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
