"""Fail-closed domain error for incomplete debate evidence."""

from src.data.evidence import EvidenceEnvelope


class EvidenceIncompleteError(RuntimeError):
    """Raised before LLM execution when required evidence is incomplete."""

    def __init__(
        self,
        envelope: EvidenceEnvelope,
        *,
        retry_after_seconds: int = 300,
    ) -> None:
        super().__init__("required evidence is incomplete")
        self.envelope = envelope
        self.retry_after_seconds = retry_after_seconds

    def detail(self) -> dict[str, object]:
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
