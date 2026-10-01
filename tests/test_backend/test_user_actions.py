"""Frozen API contract for immutable user actions."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from src.retro.user_action_ledger import UserActionLedger, UserActionLedgerError


def _payload(**updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "client_action_id": "web-001",
        "session_id": "debate-001",
        "stock_code": "300199",
        "action": "watch",
        "occurred_at": datetime(2026, 10, 1, 9, 30, tzinfo=UTC).isoformat(),
    }
    payload.update(updates)
    return payload


def test_write_query_and_idempotent_retry_contract(client, tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    callback_engine = AsyncMock()
    callback_engine.dispatch.return_value = []
    headers = {"X-User-Id": "local-user"}

    with (
        patch("backend.routers.user_actions._get_ledger", return_value=ledger),
        patch(
            "backend.routers.user_actions._get_callback_engine",
            return_value=callback_engine,
        ),
    ):
        created = client.post("/api/user/action", headers=headers, json=_payload())
        replayed = client.post("/api/user/action", headers=headers, json=_payload())
        listed = client.get("/api/user/actions", headers=headers)

    assert created.status_code == 201
    assert created.json()["meta"] == {
        "status": "recorded",
        "immutable": True,
        "retry_mode": "idempotent",
    }
    event = created.json()["data"]
    assert event["source"] == "user_reported"
    assert event["quantity"] is None
    assert event["execution_price"] is None
    assert event["ai_snapshot_status"] == "unverified"

    assert replayed.status_code == 201
    assert replayed.json()["meta"]["status"] == "replayed"
    assert replayed.json()["data"]["event_id"] == event["event_id"]
    callback_engine.dispatch.assert_awaited_once()

    assert listed.status_code == 200
    assert listed.json()["meta"]["total"] == 1
    assert listed.json()["data"] == [event]


def test_same_id_with_changed_facts_returns_non_retryable_conflict(client, tmp_path) -> None:
    ledger = UserActionLedger(tmp_path / "actions.sqlite3")
    headers = {"X-User-Id": "local-user"}
    with patch("backend.routers.user_actions._get_ledger", return_value=ledger):
        assert client.post("/api/user/action", headers=headers, json=_payload()).status_code == 201
        conflict = client.post(
            "/api/user/action",
            headers=headers,
            json=_payload(action="ignore"),
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"] == {
        "code": "USER_ACTION_IDEMPOTENCY_CONFLICT",
        "message": "同一操作标识已用于不同事实，请生成新的 client_action_id",
        "retryable": False,
    }


def test_user_header_is_required_and_validated(client) -> None:
    missing = client.post("/api/user/action", json=_payload())
    invalid = client.post(
        "/api/user/action",
        headers={"X-User-Id": "../other-user"},
        json=_payload(),
    )
    assert missing.status_code == 422
    assert invalid.status_code == 422


def test_unknown_financial_fields_are_rejected_instead_of_silently_stored(client) -> None:
    response = client.post(
        "/api/user/action",
        headers={"X-User-Id": "local-user"},
        json=_payload(actual_return_pct=0, fee_amount=0),
    )
    assert response.status_code == 422


def test_storage_failure_is_explicit_and_safe_to_retry(client) -> None:
    ledger = AsyncMock()
    ledger.append.side_effect = UserActionLedgerError("disk unavailable")
    with patch("backend.routers.user_actions._get_ledger", return_value=ledger):
        response = client.post(
            "/api/user/action",
            headers={"X-User-Id": "local-user"},
            json=_payload(),
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "USER_ACTION_LEDGER_UNAVAILABLE"
    assert response.json()["error"]["retryable"] is True


def test_openapi_freezes_write_query_and_error_models(client) -> None:
    schema = client.get("/openapi.json").json()
    write = schema["paths"]["/api/user/action"]["post"]
    query = schema["paths"]["/api/user/actions"]["get"]

    assert write["responses"]["201"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/UserActionWriteResponse"
    )
    assert write["responses"]["409"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/UserActionErrorResponse"
    )
    assert query["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/UserActionListResponse"
    )
    event = schema["components"]["schemas"]["UserActionEvent"]
    assert event["properties"]["schema_version"]["const"] == "1"
    assert event["properties"]["source"]["const"] == "user_reported"
    assert schema["paths"]["/api/retro/{record_id}/action"]["put"]["deprecated"] is True
