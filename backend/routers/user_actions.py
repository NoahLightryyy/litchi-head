"""Manual user-action write and query API."""

from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Header, Query
from fastapi.responses import JSONResponse

from src.callback.engine import ResultCallbackEngine
from src.callback.models import CallbackEventType
from src.retro.user_action_ledger import (
    UserActionConflictError,
    UserActionLedger,
    UserActionLedgerError,
)
from src.retro.user_actions import (
    UserActionCreate,
    UserActionErrorResponse,
    UserActionListMeta,
    UserActionListResponse,
    UserActionWriteMeta,
    UserActionWriteResponse,
)

logger = logging.getLogger("backend.user_actions")
router = APIRouter(prefix="/api/user")

_ledger: UserActionLedger | None = None
_callback_engine: ResultCallbackEngine | None = None


def _get_ledger() -> UserActionLedger:
    global _ledger
    if _ledger is None:
        _ledger = UserActionLedger(
            os.getenv("LITCHI_USER_ACTION_DATABASE", "data/user_profiles/actions.sqlite3")
        )
    return _ledger


def _get_callback_engine() -> ResultCallbackEngine:
    global _callback_engine
    if _callback_engine is None:
        _callback_engine = ResultCallbackEngine()
    return _callback_engine


def _error(*, status: int, code: str, message: str, retryable: bool) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": code, "message": message, "retryable": retryable}},
    )


@router.post(
    "/action",
    response_model=UserActionWriteResponse,
    status_code=201,
    responses={
        409: {"model": UserActionErrorResponse},
        503: {"model": UserActionErrorResponse},
    },
)
async def record_user_action(
    payload: UserActionCreate,
    user_id: str = Header(
        alias="X-User-Id",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
) -> UserActionWriteResponse | JSONResponse:
    """Persist one immutable fact event; safe retries reuse ``client_action_id``."""
    try:
        event, replayed = await _get_ledger().append(user_id=user_id, action=payload)
    except UserActionConflictError:
        return _error(
            status=409,
            code="USER_ACTION_IDEMPOTENCY_CONFLICT",
            message="同一操作标识已用于不同事实，请生成新的 client_action_id",
            retryable=False,
        )
    except UserActionLedgerError:
        logger.exception("用户操作账本写入失败: user=%s", user_id)
        return _error(
            status=503,
            code="USER_ACTION_LEDGER_UNAVAILABLE",
            message="用户操作暂未保存，请使用相同 client_action_id 重试",
            retryable=True,
        )

    if not replayed:
        try:
            await _get_callback_engine().dispatch(
                CallbackEventType.USER_ACTION_RECORDED,
                context=event.model_dump(mode="json"),
                source="backend.user_actions",
            )
        except Exception:
            logger.exception("用户操作已持久化，但回调分发失败: event=%s", event.event_id)

    return UserActionWriteResponse(
        data=event,
        meta=UserActionWriteMeta(status="replayed" if replayed else "recorded"),
    )


@router.get(
    "/actions",
    response_model=UserActionListResponse,
    responses={503: {"model": UserActionErrorResponse}},
)
async def list_user_actions(
    user_id: str = Header(
        alias="X-User-Id",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
    stock_code: str | None = Query(default=None, pattern=r"^\d{6}$"),
    session_id: str | None = Query(default=None, min_length=1, max_length=128),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> UserActionListResponse | JSONResponse:
    """Read only the caller-selected user's immutable events."""
    try:
        events, total = await _get_ledger().list_events(
            user_id=user_id,
            stock_code=stock_code,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
    except UserActionLedgerError:
        logger.exception("用户操作账本查询失败: user=%s", user_id)
        return _error(
            status=503,
            code="USER_ACTION_LEDGER_UNAVAILABLE",
            message="用户操作记录暂不可用，请稍后重试",
            retryable=True,
        )
    return UserActionListResponse(
        data=events,
        meta=UserActionListMeta(total=total, limit=limit, offset=offset),
    )


__all__ = ["router"]
