"""Frozen v1 preview endpoint. No account attestation is configured by default."""

import logging
from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from backend.capital_preview import ContextResolver, calculate_preview
from backend.policy_capital_contract import (
    ContractError,
    EvidencePackage,
    ExecutionPreview,
    ExecutionRequest,
)

logger = logging.getLogger(__name__)


class ContractRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError:
                error = ContractError(
                    code="VALIDATION_ERROR",
                    message="请求字段不符合本金测算契约",
                    retryable=False,
                    retry_after_seconds=None,
                )
                return JSONResponse(status_code=422, content=error.model_dump(mode="json"))

        return handler


def create_router(
    resolver: ContextResolver | None = None,
    package_resolver: Callable[[str], EvidencePackage | None] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/research", tags=["capital-preview"], route_class=ContractRoute)

    @router.post(
        "/execution-preview",
        response_model=ExecutionPreview,
        responses={
            404: {"model": ContractError, "description": "Evidence package not found"},
            422: {"model": ContractError, "description": "Invalid contract input"},
            503: {"model": ContractError, "description": "Verification service unavailable"},
        },
    )
    def preview(request: ExecutionRequest) -> ExecutionPreview | JSONResponse:
        try:
            if package_resolver is not None:
                package = package_resolver(request.evidence_package_id)
                if package is None:
                    error = ContractError(
                        code="PACKAGE_NOT_FOUND",
                        message="证据包不存在",
                        retryable=False,
                        retry_after_seconds=None,
                    )
                    return JSONResponse(status_code=404, content=error.model_dump(mode="json"))
                if (package.subject_kind, package.subject_id) != (
                    request.instrument_kind,
                    request.symbol,
                ):
                    return ExecutionPreview(
                        status="blocked",
                        evidence_package_id=request.evidence_package_id,
                        quantity=None,
                        estimated_cost=None,
                        remaining_cash=None,
                        gaps=["证据包与交易标的不匹配"],
                    )
            context = resolver(request) if resolver else None
            return calculate_preview(request, context)
        except Exception:
            logger.exception("Capital execution preview verification failed")
            error = ContractError(
                code="SOURCE_UNAVAILABLE",
                message="本金测算核验服务暂不可用",
                retryable=True,
                retry_after_seconds=None,
            )
            return JSONResponse(status_code=503, content=error.model_dump(mode="json"))

    return router


router = create_router()
