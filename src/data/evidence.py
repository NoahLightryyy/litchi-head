"""统一多源证据契约。

本模块只定义来源接入和完整性判断的稳定边界，不负责具体网络请求。
旧 ``DataSource`` Provider 可以逐个通过适配器迁移，而业务层始终只依赖这里的契约。
"""

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Generic, Protocol, TypeVar

from pydantic import BaseModel, Field, model_validator


class EvidenceCapability(str, Enum):
    """数据源可以声明支持的证据类别。"""

    REALTIME_QUOTE = "realtime_quote"
    KLINE = "kline"
    NEWS = "news"
    INDUSTRY = "industry"
    ANNOUNCEMENT = "announcement"
    FINANCIALS = "financials"
    CAPITAL_FLOW = "capital_flow"
    MARKET_SENTIMENT = "market_sentiment"


class SourceStatus(str, Enum):
    """一次来源查询的明确结果，失败绝不能伪装为空结果。"""

    SUCCESS_DATA = "success_data"
    SUCCESS_EMPTY = "success_empty"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"
    STALE = "stale"
    CONFLICTED = "conflicted"


class SourceDescriptor(BaseModel):
    """来源身份及其真实上游，用于判断来源是否独立。"""

    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    capabilities: set[EvidenceCapability] = Field(min_length=1)
    discovery_only: bool = False


class EvidenceRequest(BaseModel):
    """所有来源适配器接收的统一查询对象。"""

    capability: EvidenceCapability
    stock_code: str = ""
    start_at: datetime | None = None
    end_at: datetime | None = None

    @model_validator(mode="after")
    def validate_time_range(self) -> "EvidenceRequest":
        if self.start_at is not None and self.end_at is not None:
            if self.start_at > self.end_at:
                raise ValueError("start_at must not be later than end_at")
        return self


ItemT = TypeVar("ItemT")


class SourceResult(BaseModel, Generic[ItemT]):
    """单个来源的一次查询结果。"""

    source_id: str = Field(min_length=1)
    upstream_id: str = Field(min_length=1)
    capability: EvidenceCapability
    status: SourceStatus
    items: list[ItemT] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    error_code: str | None = None
    error_message: str | None = None

    @model_validator(mode="after")
    def validate_status_payload(self) -> "SourceResult[ItemT]":
        if self.status is SourceStatus.SUCCESS_DATA and not self.items:
            raise ValueError("SUCCESS_DATA requires at least one item")

        statuses_without_items = {
            SourceStatus.SUCCESS_EMPTY,
            SourceStatus.FAILED,
            SourceStatus.UNSUPPORTED,
        }
        if self.status in statuses_without_items and self.items:
            raise ValueError(f"{self.status.name} cannot contain items")

        if self.status is SourceStatus.FAILED and not self.error_message:
            raise ValueError("FAILED requires error_message")

        return self


class EvidenceSource(Protocol):
    """未来所有免费或付费来源都实现的最小接口。"""

    descriptor: SourceDescriptor

    def fetch(self, request: EvidenceRequest) -> SourceResult[Any]:
        """查询一种证据并返回显式状态。"""
        ...


class EvidencePolicy(BaseModel):
    """某类证据进入业务链前必须满足的完整性规则。"""

    capability: EvidenceCapability
    min_independent_upstreams: int = Field(ge=1)
    required_upstream_ids: set[str] = Field(default_factory=set)


class EvidenceAssessment(BaseModel):
    """多源查询结果的完整性判断。"""

    capability: EvidenceCapability
    complete: bool
    successful_upstream_ids: set[str] = Field(default_factory=set)
    successful_source_ids: set[str] = Field(default_factory=set)
    failed_source_ids: set[str] = Field(default_factory=set)
    discovery_only_source_ids: set[str] = Field(default_factory=set)
    unusable_source_ids: set[str] = Field(default_factory=set)
    missing_required_upstream_ids: set[str] = Field(default_factory=set)
    missing_independent_upstreams: int = Field(ge=0)


class EvidenceSourceRegistry:
    """配置驱动的来源注册中心与独立性评估器。"""

    def __init__(self) -> None:
        self._sources: dict[str, EvidenceSource] = {}

    def register(self, source: EvidenceSource) -> None:
        """注册一个适配器；来源标识重复时显式拒绝。"""
        source_id = source.descriptor.source_id
        if source_id in self._sources:
            raise ValueError(f"duplicate source_id: {source_id}")
        self._sources[source_id] = source

    def sources_for(self, capability: EvidenceCapability) -> tuple[EvidenceSource, ...]:
        """返回声明支持指定能力的来源，保持注册顺序。"""
        return tuple(
            source
            for source in self._sources.values()
            if capability in source.descriptor.capabilities
        )

    def assess(
        self,
        policy: EvidencePolicy,
        results: list[SourceResult[Any]],
    ) -> EvidenceAssessment:
        """按真实上游而不是适配器数量判断证据是否完整。"""
        successful_upstream_ids: set[str] = set()
        successful_source_ids: set[str] = set()
        failed_source_ids: set[str] = set()
        discovery_only_source_ids: set[str] = set()
        unusable_source_ids: set[str] = set()
        seen_source_ids: set[str] = set()

        successful_statuses = {
            SourceStatus.SUCCESS_DATA,
            SourceStatus.SUCCESS_EMPTY,
        }

        for result in results:
            if result.source_id in seen_source_ids:
                raise ValueError(f"duplicate result for source_id: {result.source_id}")
            seen_source_ids.add(result.source_id)

            source = self._sources.get(result.source_id)
            if source is None:
                raise ValueError(f"unregistered source_id: {result.source_id}")

            descriptor = source.descriptor
            if result.upstream_id != descriptor.upstream_id:
                raise ValueError(
                    f"result upstream {result.upstream_id!r} does not match "
                    f"registered upstream {descriptor.upstream_id!r}"
                )
            if result.capability is not policy.capability:
                raise ValueError(
                    f"result capability {result.capability.value!r} does not match "
                    f"policy capability {policy.capability.value!r}"
                )
            if policy.capability not in descriptor.capabilities:
                raise ValueError(
                    f"source {result.source_id!r} does not declare "
                    f"{policy.capability.value!r}"
                )

            if descriptor.discovery_only:
                discovery_only_source_ids.add(result.source_id)
                continue

            if result.status in successful_statuses:
                successful_source_ids.add(result.source_id)
                successful_upstream_ids.add(result.upstream_id)
            else:
                unusable_source_ids.add(result.source_id)
                if result.status is SourceStatus.FAILED:
                    failed_source_ids.add(result.source_id)

        missing_required = (
            policy.required_upstream_ids - successful_upstream_ids
        )
        missing_independent = max(
            0,
            policy.min_independent_upstreams - len(successful_upstream_ids),
        )
        complete = not missing_required and missing_independent == 0

        return EvidenceAssessment(
            capability=policy.capability,
            complete=complete,
            successful_upstream_ids=successful_upstream_ids,
            successful_source_ids=successful_source_ids,
            failed_source_ids=failed_source_ids,
            discovery_only_source_ids=discovery_only_source_ids,
            unusable_source_ids=unusable_source_ids,
            missing_required_upstream_ids=missing_required,
            missing_independent_upstreams=missing_independent,
        )


__all__ = [
    "EvidenceAssessment",
    "EvidenceCapability",
    "EvidencePolicy",
    "EvidenceRequest",
    "EvidenceSource",
    "EvidenceSourceRegistry",
    "SourceDescriptor",
    "SourceResult",
    "SourceStatus",
]
