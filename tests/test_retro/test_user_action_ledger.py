"""Immutable user-action ledger persistence and isolation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.retro.user_action_ledger import UserActionConflictError, UserActionLedger
from src.retro.user_actions import UserActionCreate


def _action(**updates: object) -> UserActionCreate:
    values: dict[str, object] = {
        "client_action_id": "browser-001",
        "session_id": "debate-001",
        "stock_code": "300199",
        "action": "watch",
        "occurred_at": datetime(2026, 10, 1, 9, 30, tzinfo=UTC),
    }
    values.update(updates)
    return UserActionCreate.model_validate(values)


@pytest.mark.asyncio
async def test_event_survives_restart_without_inventing_missing_money_fields(tmp_path) -> None:
    database = tmp_path / "actions.sqlite3"
    first = UserActionLedger(database)

    written, replayed = await first.append(user_id="local-user", action=_action())

    assert not replayed
    assert written.quantity is None
    assert written.execution_price is None
    assert written.currency is None
    assert written.ai_snapshot_status.value == "unverified"
    assert written.limitations == [
        "ai_snapshot_not_verified",
        "user_identity_not_authenticated",
    ]

    restarted = UserActionLedger(database)
    events, total = await restarted.list_events(user_id="local-user")
    assert total == 1
    assert events == [written]


@pytest.mark.asyncio
async def test_identical_retry_replays_but_changed_facts_conflict(tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    original, first_replay = await ledger.append(user_id="u1", action=_action())
    retried, second_replay = await ledger.append(user_id="u1", action=_action())

    assert not first_replay
    assert second_replay
    assert retried == original

    with pytest.raises(UserActionConflictError):
        await ledger.append(user_id="u1", action=_action(action="ignore"))


@pytest.mark.asyncio
async def test_equivalent_decimal_spelling_is_an_idempotent_retry(tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    first = _action(quantity="100.0", execution_price="12.340", currency="CNY")
    second = _action(quantity="100.00", execution_price="12.34", currency="CNY")

    original, _ = await ledger.append(user_id="u1", action=first)
    retried, replayed = await ledger.append(user_id="u1", action=second)

    assert replayed
    assert retried == original


@pytest.mark.asyncio
async def test_users_are_isolated_even_when_client_ids_match(tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    first, _ = await ledger.append(user_id="user-a", action=_action())
    second, _ = await ledger.append(user_id="user-b", action=_action())

    a_events, a_total = await ledger.list_events(user_id="user-a")
    b_events, b_total = await ledger.list_events(user_id="user-b")

    assert a_total == b_total == 1
    assert a_events == [first]
    assert b_events == [second]
    assert first.event_id != second.event_id


@pytest.mark.asyncio
async def test_concurrent_identical_retries_create_one_event(tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")

    results = await asyncio.gather(*[
        ledger.append(user_id="u1", action=_action())
        for _ in range(5)
    ])
    events, total = await ledger.list_events(user_id="u1")

    assert total == 1
    assert len(events) == 1
    assert len({event.event_id for event, _ in results}) == 1
    assert sum(replayed for _, replayed in results) == 4


@pytest.mark.asyncio
async def test_query_filters_without_cross_user_leakage(tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    await ledger.append(user_id="u1", action=_action())
    await ledger.append(
        user_id="u1",
        action=_action(
            client_action_id="browser-002",
            session_id="debate-002",
            stock_code="000001",
        ),
    )
    await ledger.append(user_id="u2", action=_action(client_action_id="browser-003"))

    events, total = await ledger.list_events(user_id="u1", stock_code="300199")

    assert total == 1
    assert [event.stock_code for event in events] == ["300199"]
    assert all(event.user_id == "u1" for event in events)


def test_money_facts_require_positive_values_and_explicit_currency() -> None:
    with pytest.raises(ValidationError, match="greater than 0"):
        _action(quantity=Decimal("0"))
    with pytest.raises(ValidationError, match="currency is required"):
        _action(execution_price=Decimal("12.34"))

    action = _action(
        quantity=Decimal("100"),
        execution_price=Decimal("12.34"),
        currency="CNY",
    )
    assert action.quantity == Decimal("100")
    assert action.execution_price == Decimal("12.34")


def test_event_time_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="occurred_at must include timezone"):
        _action(occurred_at=datetime(2026, 10, 1, 9, 30))
