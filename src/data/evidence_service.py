"""多通道证据并发汇总与统一打包服务。"""

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from src.data.evidence import (
    EvidenceEnvelope,
    EvidencePolicy,
    EvidenceRequest,
    EvidenceSource,
    EvidenceSourceRegistry,
    SourceResult,
    SourceStatus,
)

logger = logging.getLogger(__name__)


def _exception_message(exc: Exception) -> str:
    return str(exc).strip() or exc.__class__.__name__


class DataEvidenceService:
    """并发调用同类证据通道并产出稳定的业务信封。"""

    def __init__(
        self,
        registry: EvidenceSourceRegistry,
        *,
        max_workers: int = 4,
    ) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be at least 1")
        self._registry = registry
        self._max_workers = max_workers

    def collect(
        self,
        request: EvidenceRequest,
        policy: EvidencePolicy,
    ) -> EvidenceEnvelope:
        """采集一种 capability，并保留完整来源诊断和统一条目。"""
        if request.capability is not policy.capability:
            raise ValueError("request and policy capability must match")

        sources = self._registry.sources_for(request.capability)
        source_results = self._fetch_all(sources, request)
        assessment = self._registry.assess(policy, source_results)
        items = self._select_business_items(sources, source_results)

        return EvidenceEnvelope(
            request=request,
            policy=policy,
            source_results=source_results,
            items=items,
            assessment=assessment,
            complete=assessment.complete,
        )

    def _fetch_all(
        self,
        sources: tuple[EvidenceSource, ...],
        request: EvidenceRequest,
    ) -> list[SourceResult[Any]]:
        if not sources:
            return []

        worker_count = min(self._max_workers, len(sources))
        with ThreadPoolExecutor(
            max_workers=worker_count,
            thread_name_prefix="evidence-source",
        ) as executor:
            futures = [
                executor.submit(self._fetch_one, source, request)
                for source in sources
            ]
            return [future.result() for future in futures]

    @staticmethod
    def _fetch_one(
        source: EvidenceSource,
        request: EvidenceRequest,
    ) -> SourceResult[Any]:
        try:
            return source.fetch(request)
        except Exception as exc:
            logger.exception(
                "证据来源抛出未处理异常: source_id=%s capability=%s",
                source.descriptor.source_id,
                request.capability.value,
            )
            return SourceResult[Any](
                source_id=source.descriptor.source_id,
                upstream_id=source.descriptor.upstream_id,
                capability=request.capability,
                status=SourceStatus.FAILED,
                error_code="source_unhandled_exception",
                error_message=_exception_message(exc),
            )

    @staticmethod
    def _select_business_items(
        sources: tuple[EvidenceSource, ...],
        results: list[SourceResult[Any]],
    ) -> list[Any]:
        """每个真实上游只输出首份成功数据，诊断结果仍全部保留。"""
        emitted_upstreams: set[str] = set()
        items: list[Any] = []

        for source, result in zip(sources, results, strict=True):
            if source.descriptor.discovery_only:
                continue
            if result.status is not SourceStatus.SUCCESS_DATA:
                continue
            if result.upstream_id in emitted_upstreams:
                continue
            emitted_upstreams.add(result.upstream_id)
            items.extend(result.items)

        return DataEvidenceService._deduplicate_items(items)

    @staticmethod
    def _deduplicate_items(items: list[Any]) -> list[Any]:
        """按股票和规范化标题跨上游去重，来源原始结果仍完整保留。"""
        seen: set[tuple[str, str]] = set()
        unique_items: list[Any] = []

        for item in items:
            title = getattr(item, "title", "")
            code = getattr(item, "code", "")
            if not isinstance(title, str) or not title.strip():
                unique_items.append(item)
                continue

            normalized_title = re.sub(r"\s+", "", title).casefold()
            key = (str(code).strip(), normalized_title)
            if key in seen:
                continue
            seen.add(key)
            unique_items.append(item)

        return unique_items


__all__ = ["DataEvidenceService"]
