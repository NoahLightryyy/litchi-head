"""存储容量基线工具测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.storage_baseline import (
    BenchmarkConfig,
    benchmark_json_object,
    benchmark_jsonl,
    benchmark_sqlite,
    build_decision_record,
    render_markdown,
    run_capacity_suite,
)


def test_benchmark_config_rejects_invalid_values() -> None:
    with pytest.raises(ValueError, match="record_count"):
        BenchmarkConfig(record_count=0)
    with pytest.raises(ValueError, match="payload_bytes"):
        BenchmarkConfig(record_count=10, payload_bytes=0)


def test_decision_record_is_deterministic_and_contains_audit_fields() -> None:
    first = build_decision_record(7, payload_bytes=512)
    second = build_decision_record(7, payload_bytes=512)

    assert first == second
    assert first["session_id"] == "bench-00000007"
    assert first["stock_code"] == "000007"
    assert first["schema_version"] == 1
    assert first["source"] == "synthetic-capacity-baseline"
    assert len(json.dumps(first, ensure_ascii=False).encode("utf-8")) >= 512


@pytest.mark.parametrize(
    ("runner", "backend"),
    [
        (benchmark_jsonl, "jsonl"),
        (benchmark_json_object, "json-object"),
        (benchmark_sqlite, "sqlite-wal"),
    ],
)
def test_storage_backends_write_and_read_all_records(
    tmp_path: Path,
    runner,
    backend: str,
) -> None:
    config = BenchmarkConfig(record_count=25, payload_bytes=256, lookup_count=10)

    result = runner(tmp_path / backend, config)

    assert result.backend == backend
    assert result.records_written == 25
    assert result.records_read == 25
    assert result.write_seconds >= 0
    assert result.lookup_p95_ms >= 0
    assert result.storage_bytes > 0
    assert result.errors == []


def test_sqlite_duplicate_session_is_idempotent(tmp_path: Path) -> None:
    config = BenchmarkConfig(record_count=10, payload_bytes=256, lookup_count=5)

    first = benchmark_sqlite(tmp_path / "sqlite", config)
    second = benchmark_sqlite(tmp_path / "sqlite", config)

    assert first.records_read == 10
    assert second.records_read == 10


def test_capacity_suite_is_json_serializable_and_markdown_readable(
    tmp_path: Path,
) -> None:
    config = BenchmarkConfig(record_count=20, payload_bytes=256, lookup_count=5)

    report = run_capacity_suite(tmp_path, config)
    encoded = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)
    markdown = render_markdown(report)

    assert "sqlite-wal" in encoded
    assert "json-object" in markdown
    assert "仅代表本机合成基线" in markdown
    assert report.environment.python_version
    assert len(report.results) == 3
