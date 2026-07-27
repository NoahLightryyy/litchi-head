"""测试 RetroStore 持久化"""

import tempfile

from src.retro.models import RetroRecord, RetroSummary
from src.retro.store import RetroStore


class TestRetroStore:
    """RetroStore CRUD 操作"""

    async def _make_store(self) -> RetroStore:
        tmp = tempfile.mkdtemp()
        return RetroStore(base_path=tmp)

    async def test_empty_store(self):
        """空存储"""
        store = await self._make_store()
        records = await store.list_records()
        assert records == []
        assert await store.count() == 0
        summary = await store.get_summary()
        assert summary.total_records == 0

    async def test_put_and_get(self):
        """写入和查询单条"""
        store = await self._make_store()
        record = RetroRecord(
            record_id="test_001",
            session_id="deb_abc",
            stock_code="000001",
            stock_name="平安银行",
            consensus="看涨",
            confidence=0.85,
        )
        await store.put(record)

        fetched = await store.get("test_001")
        assert fetched is not None
        assert fetched.stock_code == "000001"
        assert fetched.stock_name == "平安银行"
        assert fetched.confidence == 0.85

    async def test_get_not_found(self):
        """查询不存在的记录"""
        store = await self._make_store()
        assert await store.get("nonexistent") is None

    async def test_list_records(self):
        """列表查询"""
        store = await self._make_store()
        records = [
            RetroRecord(record_id="1", session_id="s", stock_code="000001", outcome="correct"),
            RetroRecord(record_id="2", session_id="s", stock_code="000002", outcome="wrong"),
            RetroRecord(record_id="3", session_id="s", stock_code="000003", outcome="pending"),
        ]
        for r in records:
            await store.put(r)

        all_records = await store.list_records()
        assert len(all_records) == 3

        filtered = await store.list_records(outcome="correct")
        assert len(filtered) == 1
        assert filtered[0].record_id == "1"

        stock_filtered = await store.list_records(stock_code="000002")
        assert len(stock_filtered) == 1

    async def test_list_pagination(self):
        """分页查询"""
        store = await self._make_store()
        for i in range(10):
            await store.put(
                RetroRecord(record_id=f"{i}", session_id="s", stock_code=f"{i:06d}")
            )

        page1 = await store.list_records(limit=3, offset=0)
        assert len(page1) == 3

        page2 = await store.list_records(limit=3, offset=3)
        assert len(page2) == 3
        # 按 created_at 降序，最新在前
        assert page1[0].record_id != page2[0].record_id

    async def test_update_action(self):
        """更新用户操作"""
        store = await self._make_store()
        r = RetroRecord(record_id="act_001", session_id="s", stock_code="000001")
        await store.put(r)

        updated = await store.update_action("act_001", "buy")
        assert updated is not None
        assert updated.user_action == "buy"
        assert updated.user_action_at is not None

    async def test_update_action_not_found(self):
        """更新不存在的记录"""
        store = await self._make_store()
        result = await store.update_action("nonexistent", "buy")
        assert result is None

    async def test_update_outcome(self):
        """更新实际结果"""
        store = await self._make_store()
        r = RetroRecord(
            record_id="out_001",
            session_id="s",
            stock_code="000001",
            consensus="Bullish",
            price_at_debate=10.0,
        )
        await store.put(r)

        updated = await store.update_outcome("out_001", actual_return_pct=5.0, actual_price=10.5)
        assert updated is not None
        assert updated.actual_return_pct == 5.0
        assert updated.actual_price == 10.5
        assert updated.outcome == "correct"

    async def test_update_outcome_not_found(self):
        """更新不存在记录的结果"""
        store = await self._make_store()
        result = await store.update_outcome("nonexistent", 1.0, 10.0)
        assert result is None

    async def test_delete(self):
        """删除记录"""
        store = await self._make_store()
        r = RetroRecord(record_id="del_001", session_id="s", stock_code="000001")
        await store.put(r)
        assert await store.count() == 1

        ok = await store.delete("del_001")
        assert ok is True
        assert await store.count() == 0
        assert await store.get("del_001") is None

    async def test_delete_not_found(self):
        """删除不存在的记录"""
        store = await self._make_store()
        assert await store.delete("nonexistent") is False

    async def test_get_summary(self):
        """聚合统计"""
        store = await self._make_store()
        records = [
            RetroRecord(
                record_id="1", session_id="s", stock_code="000001",
                outcome="correct", confidence=0.8, weighted_score=80,
            ),
            RetroRecord(
                record_id="2", session_id="s", stock_code="000002",
                outcome="wrong", confidence=0.6, weighted_score=60,
            ),
            RetroRecord(
                record_id="3", session_id="s", stock_code="000003",
                outcome="pending", confidence=0.9, weighted_score=90,
            ),
        ]
        for r in records:
            await store.put(r)

        summary = await store.get_summary()
        assert isinstance(summary, RetroSummary)
        assert summary.total_records == 3
        assert summary.closed_records == 2
        assert summary.win_count == 1
        assert summary.loss_count == 1
        assert summary.win_rate == 0.5
