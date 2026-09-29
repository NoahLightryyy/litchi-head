"""Single background board warm-up, using the same bounded production provider."""
from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src.data.board_store import BoardSnapshotStore
from src.data.providers.eastmoney_boards import BoardKind, EastmoneyBoardSnapshots

logger = logging.getLogger(__name__)


def configure_board_store(provider: EastmoneyBoardSnapshots) -> None:
    """Configure lazily at startup, with a workspace-relative durable default."""
    path = Path(os.getenv("LITCHI_BOARD_DATABASE", "data/evidence/boards.db"))
    provider.store = BoardSnapshotStore(path)


def collect_boards_once(provider: EastmoneyBoardSnapshots) -> dict[str, bool]:
    """Failure of either category cannot suppress collection of the other."""
    def collect(kind: BoardKind) -> bool:
        try:
            return bool(provider.fetch(kind).quotes)
        except Exception:
            logger.exception("Background board collection failed: category=%s", kind)
            return False
    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="board-warmup") as pool:
        futures = {kind: pool.submit(collect, kind) for kind in ("industry", "concept")}
        return {kind: future.result() for kind, future in futures.items()}


async def warm_boards(provider: EastmoneyBoardSnapshots) -> None:
    """Start once without blocking serving; join bounded I/O before shutdown."""
    task = asyncio.create_task(asyncio.to_thread(collect_boards_once, provider))
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise
