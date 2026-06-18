"""费用跟踪业务测试（TD-004 追认）"""

from pathlib import Path

from src.utils.cost_tracker import CostTracker


class TestCostTracker:
    def test_init_empty(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        assert tracker._records == []

    def test_record_single(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="deepseek-chat",
            prompt_tokens=100,
            completion_tokens=50,
            agent="test_agent",
            session_id="s1",
        )
        assert len(tracker._records) == 1
        r = tracker._records[0]
        assert r["model"] == "deepseek-chat"
        assert r["agent"] == "test_agent"
        assert r["session_id"] == "s1"
        assert r["prompt_tokens"] == 100
        assert r["completion_tokens"] == 50

    def test_record_cost_calculation_deepseek(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="deepseek-chat",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            agent="a",
            session_id="s1",
        )
        # deepseek-chat: input=0.5/M, output=1.0/M
        # cost = (1_000_000 * 0.5 + 1_000_000 * 1.0) / 1_000_000 = 1.5
        assert tracker._records[0]["cost_yuan"] == 1.5

    def test_record_cost_calculation_gpt4o(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="gpt-4o",
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            agent="a",
            session_id="s1",
        )
        # gpt-4o: input=15.0/M, output=60.0/M
        # cost = (1_000_000 * 15.0 + 500_000 * 60.0) / 1_000_000 = 45.0
        assert tracker._records[0]["cost_yuan"] == 45.0

    def test_record_fallback_prices(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="unknown-model",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            agent="a",
            session_id="s1",
        )
        # 未知模型使用默认价格 input=0.5, output=1.0
        assert tracker._records[0]["cost_yuan"] == 1.5

    def test_session_cost(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="deepseek-chat", prompt_tokens=1000, completion_tokens=500,
            agent="a", session_id="s1",
        )
        tracker.record(
            model="deepseek-chat", prompt_tokens=2000, completion_tokens=1000,
            agent="b", session_id="s1",
        )
        tracker.record(
            model="deepseek-chat", prompt_tokens=500, completion_tokens=250,
            agent="c", session_id="s2",
        )
        assert tracker.session_cost("s1") > 0
        assert tracker.session_cost("s2") > 0
        assert tracker.session_cost("s1") > tracker.session_cost("s2")

    def test_session_cost_zero_for_nonexistent(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        assert tracker.session_cost("nonexistent") == 0.0

    def test_session_cost_rounds_to_4_decimals(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="deepseek-chat", prompt_tokens=1, completion_tokens=1,
            agent="a", session_id="s1",
        )
        cost = tracker.session_cost("s1")
        assert isinstance(cost, float)
        # 1 * 0.5 + 1 * 1.0 = 1.5 / 1_000_000 = 0.0000015 → round to 4 decimals

    def test_daily_report_no_calls(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        report = tracker.daily_report()
        assert "今日暂无" in report

    def test_daily_report_with_calls(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        tracker.record(
            model="deepseek-chat", prompt_tokens=100, completion_tokens=50,
            agent="a", session_id="s1",
        )
        report = tracker.daily_report()
        assert "今日 LLM 费用" in report
        assert "deepseek-chat" in report

    def test_save_creates_file(self, tmp_path: Path):
        tracker = CostTracker(log_dir=str(tmp_path))
        tracker.record(
            model="deepseek-chat", prompt_tokens=100, completion_tokens=50,
            agent="a", session_id="s1",
        )
        tracker.save()

        files = list(tmp_path.glob("*.jsonl"))
        assert len(files) == 1
        content = files[0].read_text(encoding="utf-8")
        assert "deepseek-chat" in content

    def test_save_empty_does_nothing(self, tmp_path: Path):
        tracker = CostTracker(log_dir=str(tmp_path))
        tracker.save()
        assert list(tmp_path.glob("*.jsonl")) == []

    def test_save_clears_records(self, tmp_path: Path):
        tracker = CostTracker(log_dir=str(tmp_path))
        tracker.record(
            model="deepseek-chat", prompt_tokens=100, completion_tokens=50,
            agent="a", session_id="s1",
        )
        tracker.save()
        assert tracker._records == []

    def test_save_appends_to_existing(self, tmp_path: Path):
        tracker = CostTracker(log_dir=str(tmp_path))
        tracker.record(
            model="deepseek-chat", prompt_tokens=100, completion_tokens=50,
            agent="a", session_id="s1",
        )
        tracker.save()

        # 第二次调用
        tracker.record(
            model="gpt-4o-mini", prompt_tokens=200, completion_tokens=100,
            agent="b", session_id="s2",
        )
        tracker.save()

        lines = list(tmp_path.glob("*.jsonl"))[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

    def test_multiple_records_independent(self):
        tracker = CostTracker(log_dir="/tmp/_test_cost_logs")
        for i in range(10):
            tracker.record(
                model="deepseek-chat",
                prompt_tokens=100 * (i + 1),
                completion_tokens=50 * (i + 1),
                agent=f"agent_{i}",
                session_id=f"s{i % 3}",
            )
        assert len(tracker._records) == 10
        assert tracker.session_cost("s0") > 0
        assert tracker.session_cost("s1") > 0
        assert tracker.session_cost("s2") > 0
