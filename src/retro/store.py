"""复盘记录持久化 —— RetroStore

基于 JSON 文件的 RetroRecord 存储。
文件位置：data/retro/records.json

使用 asyncio.Lock 保证并发安全。
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.retro.models import RetroRecord, RetroSummary, compute_retro_summary


class RetroStore:
    """复盘记录存储

    读写 data/retro/records.json，每条记录按 record_id 索引。
    """

    def __init__(self, base_path: str | Path = "data/retro"):
        self._file_path = Path(base_path) / "records.json"
        self._lock = asyncio.Lock()

    async def _read_all(self) -> dict[str, dict[str, Any]]:
        """读取全部记录（JSON 对象）"""
        if not self._file_path.exists():
            return {}
        try:
            async with self._lock:
                with open(self._file_path, encoding="utf-8") as f:
                    return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    async def _write_all(self, data: dict[str, dict[str, Any]]) -> None:
        """覆写文件"""
        self._file_path.parent.mkdir(parents=True, exist_ok=True)
        async with self._lock:
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    async def put(self, record: RetroRecord) -> RetroRecord:
        """写入/覆盖一条记录

        Args:
            record: 复盘记录

        Returns:
            写入后的记录
        """
        all_records = await self._read_all()
        all_records[record.record_id] = record.model_dump(mode="json")
        await self._write_all(all_records)
        return record

    async def get(self, record_id: str) -> RetroRecord | None:
        """按 ID 查询单条记录

        Args:
            record_id: 记录 ID

        Returns:
            RetroRecord 或 None
        """
        all_records = await self._read_all()
        raw = all_records.get(record_id)
        if raw is None:
            return None
        return RetroRecord(**raw)

    async def list_records(
        self,
        stock_code: str | None = None,
        outcome: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RetroRecord]:
        """列出复盘记录（按 created_at 降序）

        Args:
            stock_code: 可选，按股票代码过滤
            outcome: 可选，按结果过滤（correct/wrong/pending）
            limit: 返回条数上限
            offset: 偏移量

        Returns:
            RetroRecord 列表
        """
        all_records = await self._read_all()
        records = [RetroRecord(**raw) for raw in all_records.values()]

        # 过滤
        if stock_code:
            records = [r for r in records if r.stock_code == stock_code]
        if outcome:
            records = [r for r in records if r.outcome == outcome]

        # 按 created_at 降序
        records.sort(key=lambda r: r.created_at, reverse=True)

        # 分页
        return records[offset : offset + limit]

    async def get_summary(self) -> RetroSummary:
        """计算聚合统计

        Returns:
            聚合统计摘要
        """
        all_records = await self._read_all()
        records = [RetroRecord(**raw) for raw in all_records.values()]
        return compute_retro_summary(records)

    async def update_action(
        self,
        record_id: str,
        user_action: str,
    ) -> RetroRecord | None:
        """更新用户操作

        Args:
            record_id: 记录 ID
            user_action: 用户操作（buy/sell/hold/skip）

        Returns:
            更新后的记录，未找到返回 None
        """
        record = await self.get(record_id)
        if record is None:
            return None
        record.user_action = user_action
        record.user_action_at = datetime.now()
        return await self.put(record)

    async def update_outcome(
        self,
        record_id: str,
        actual_return_pct: float,
        actual_price: float,
    ) -> RetroRecord | None:
        """更新实际结果并自动判定 outcome

        Args:
            record_id: 记录 ID
            actual_return_pct: 实际涨跌幅（%）
            actual_price: 当前价格

        Returns:
            更新后的记录，未找到返回 None
        """
        record = await self.get(record_id)
        if record is None:
            return None

        # 补充前判断：如果已有关闭结果，跳过
        if record.outcome != "pending":
            return record

        record.actual_return_pct = round(actual_return_pct, 4)
        record.actual_price = actual_price

        # 根据共识方向判定正确/错误
        from src.retro.models import compute_outcome

        record.outcome = compute_outcome(
            direction=record.consensus or "Neutral",
            return_pct=actual_return_pct,
        )
        return await self.put(record)

    async def delete(self, record_id: str) -> bool:
        """删除一条记录

        Args:
            record_id: 记录 ID

        Returns:
            是否删除成功
        """
        all_records = await self._read_all()
        if record_id not in all_records:
            return False
        del all_records[record_id]
        await self._write_all(all_records)
        return True

    async def count(self) -> int:
        """记录总数"""
        all_records = await self._read_all()
        return len(all_records)


__all__ = ["RetroStore"]
