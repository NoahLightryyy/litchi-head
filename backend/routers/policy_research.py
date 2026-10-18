"""Frozen evidence/job HTTP interface; lifecycle owns durable task recovery."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.responses import Response

from backend.policy_capital_contract import (
    ContractError,
    EvidencePackage,
    ResearchJob,
    ResearchRequest,
)
from backend.policy_evidence import EvidenceRepository
from backend.policy_research import PolicyResearchService, ResearchStore

logger = logging.getLogger(__name__)
_runtime: PolicyResearchService | None = None


def error(code: str, message: str, status: int) -> JSONResponse:
    body = ContractError.model_validate(
        dict(
            code=code,
            message=message,
            retryable=code == "SOURCE_UNAVAILABLE",
            retry_after_seconds=None,
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


class ContractRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except RequestValidationError:
                return error("VALIDATION_ERROR", "请求字段不符合冻结契约，请检查输入。", 422)
            except KeyError:
                return error("PACKAGE_NOT_FOUND", "未找到该版本证据包或研究任务。", 404)
            except ValueError as exc:
                if str(exc) == "IDEMPOTENCY_CONFLICT":
                    return error(
                        "IDEMPOTENCY_CONFLICT", "该提交键已用于不同请求，请检查原任务。", 409
                    )
                if str(exc) == "VALIDATION_ERROR":
                    return error("VALIDATION_ERROR", "标的身份与证据包不匹配。", 422)
                logger.exception("Policy contract data invalid")
                return error("SOURCE_UNAVAILABLE", "证据档案校验失败，请稍后重试。", 503)
            except Exception:
                logger.exception("Policy research endpoint unavailable")
                return error("SOURCE_UNAVAILABLE", "研究服务或证据档案暂不可用，请稍后重试。", 503)

        return wrapped


async def start_runtime(path: Path | None = None) -> None:
    """Call once from main lifespan, single backend worker only."""
    global _runtime
    if _runtime is None:
        store = ResearchStore(path or Path("data/policy_research.sqlite3"))
        store.recover_interrupted()
        _runtime = PolicyResearchService(store)


async def stop_runtime() -> None:
    global _runtime
    if _runtime is not None:
        await _runtime.close()
        _runtime = None


def create_router(service: PolicyResearchService | None = None) -> APIRouter:
    routes = APIRouter(prefix="/api/research", route_class=ContractRoute)
    responses: dict[int | str, dict[str, Any]] = {
        status: {"model": ContractError} for status in (404, 409, 422, 503)
    }

    def active() -> PolicyResearchService:
        selected = service or _runtime
        if selected is None:
            raise OSError("Research lifecycle not started")
        return selected

    @routes.get("/evidence/{package_id}", response_model=EvidencePackage, responses=responses)
    async def evidence(package_id: str) -> EvidencePackage:
        repository = service.repository if service else EvidenceRepository()
        return repository.get(package_id)

    @routes.post("/jobs", response_model=ResearchJob, status_code=202, responses=responses)
    async def submit(body: ResearchRequest) -> ResearchJob:
        selected = active()
        job, created = selected.submit(body)
        if created:
            selected.schedule(job.job_id)
        return job

    @routes.get("/jobs/{job_id}", response_model=ResearchJob, responses=responses)
    async def read(job_id: str) -> ResearchJob:
        return active().store.get(job_id)

    return routes


router = create_router()
