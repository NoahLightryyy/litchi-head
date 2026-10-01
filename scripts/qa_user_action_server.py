"""Isolated browser fault harness; never mount in backend.main.

Requires QA_ACTION_DIR, uses only a dedicated SQLite file and qa-fault-* owners.
control.txt: normal or delay_after_commit (60s response delay after durable write).
Requests are recorded for idempotency evidence, containing QA facts only.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import RequestResponseEndpoint

from backend.routers import user_actions
from src.retro.user_action_ledger import UserActionLedger

qa_dir = Path(os.environ["QA_ACTION_DIR"]).resolve()
qa_dir.mkdir(parents=True, exist_ok=True)
user_actions._ledger = UserActionLedger(str(qa_dir / "qa-actions.sqlite3"))
app = FastAPI()
RESPONSE_DELAY_SECONDS = 60


@app.middleware("http")
async def record_qa_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    owner = request.headers.get("X-User-Id", "")
    if request.method != "OPTIONS" and not owner.startswith("qa-fault-"):
        return JSONResponse(status_code=403, content={"error": "QA owners only"})
    if request.method == "POST" and request.url.path == "/api/user/action":
        payload = await request.json()
        with (qa_dir / "requests.jsonl").open("a", encoding="utf-8") as stream:
            record = json.dumps({"owner": owner, "payload": payload}, ensure_ascii=False)
            stream.write(record + "\n")
        response = await call_next(request)
        mode = (qa_dir / "control.txt").read_text(encoding="utf-8").strip()
        if mode == "delay_after_commit" and response.status_code == 201:
            await asyncio.sleep(RESPONSE_DELAY_SECONDS)
        return response
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3037", "http://127.0.0.1:3037"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-User-Id"],
)
app.include_router(user_actions.router)
