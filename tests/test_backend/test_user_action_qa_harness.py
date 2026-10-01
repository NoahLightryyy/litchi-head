"""The fault harness must stay isolated; these are not browser acceptance tests."""

import importlib.util
import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.routers import user_actions


def test_fault_harness_uses_dedicated_ledger_and_real_conflicts(tmp_path, monkeypatch):
    monkeypatch.setenv("QA_ACTION_DIR", str(tmp_path))
    monkeypatch.setattr(user_actions, "_ledger", None)
    monkeypatch.setattr(user_actions, "_callback_engine", None)
    path = Path(__file__).parents[2] / "scripts" / "qa_user_action_server.py"
    spec = importlib.util.spec_from_file_location("qa_harness_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.RESPONSE_DELAY_SECONDS = 0
    (tmp_path / "control.txt").write_text("delay_after_commit", encoding="utf-8")
    headers = {"X-User-Id": "qa-fault-unit"}
    payload = {
        "client_action_id": "qa-original-id",
        "session_id": "QA-only-not-trade",
        "stock_code": "300199",
        "action": "watch",
        "occurred_at": "2026-10-01T10:30:00+08:00",
    }
    with TestClient(module.app) as client:
        assert client.post("/api/user/action", json=payload).status_code == 403
        first = client.post("/api/user/action", json=payload, headers=headers)
        assert first.status_code == 201
        assert (tmp_path / "qa-actions.sqlite3").exists()
        assert first.json()["meta"]["status"] == "recorded"
        replay = client.post("/api/user/action", json=payload, headers=headers)
        assert replay.json()["meta"]["status"] == "replayed"
        conflict = client.post(
            "/api/user/action", json={**payload, "action": "ignore"}, headers=headers
        )
        assert conflict.status_code == 409
        own = client.get("/api/user/actions", headers=headers).json()
        assert own["meta"]["total"] == 1
        other = client.get("/api/user/actions", headers={"X-User-Id": "qa-fault-other"})
        assert other.json()["meta"]["total"] == 0
    records = [json.loads(line) for line in (tmp_path / "requests.jsonl").read_text(
        encoding="utf-8"
    ).splitlines()]
    assert len(records) == 3
    assert {r["payload"]["client_action_id"] for r in records} == {"qa-original-id"}
