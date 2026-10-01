"""Domain error for evidence that is corrupted or conflicting and cannot be used."""

from src.data.evidence import EvidenceEnvelope
from src.data.kline_business import KlineBusinessFailure


class EvidenceIncompleteError(RuntimeError):
    """Raised before LLM execution when evidence is unsafe, not merely incomplete."""

    def __init__(
        self,
        envelope: EvidenceEnvelope | KlineBusinessFailure | dict[str, object],
        *,
        retry_after_seconds: int = 300,
    ) -> None:
        super().__init__("required evidence is incomplete")
        self.envelope = envelope
        self.retry_after_seconds = retry_after_seconds

    def detail(self) -> dict[str, object]:
        if isinstance(self.envelope, KlineBusinessFailure):
            return {
                "capability": "kline_business",
                "error_codes": list(self.envelope.error_codes),
                "layer_diagnostics": [
                    item.model_dump(mode="json")
                    for item in self.envelope.layer_diagnostics
                ],
                "retry_after_seconds": self.retry_after_seconds,
                "collected_at": self.envelope.as_of.isoformat(),
            }
        if isinstance(self.envelope, dict):
            return {**self.envelope, "retry_after_seconds": self.retry_after_seconds}
        assessment = self.envelope.assessment
        missing = set(assessment.missing_required_upstream_ids)
        for result in self.envelope.source_results:
            if result.source_id in assessment.unusable_source_ids:
                missing.add(result.upstream_id)
        return {
            "capability": self.envelope.request.capability.value,
            "missing_upstream_ids": sorted(missing),
            "missing_independent_upstreams": (
                assessment.missing_independent_upstreams
            ),
            "retry_after_seconds": self.retry_after_seconds,
            "collected_at": self.envelope.collected_at.isoformat(),
        }


__all__ = ["EvidenceIncompleteError"]
