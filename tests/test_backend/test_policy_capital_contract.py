from datetime import date

import pytest
from pydantic import ValidationError

from backend.policy_capital_contract import (
    Claim,
    ContractError,
    EvidencePackage,
    HoldingsDisclosure,
)


def test_unsupported_factual_claim_is_rejected():
    with pytest.raises(ValidationError):
        Claim(id="c", text="benefits", assessment="supported", evidence_ids=[], limitations=[])


def test_dangling_reference_is_rejected():
    with pytest.raises(ValidationError):
        EvidencePackage(package_id="p", subject_kind="stock", subject_id="688012",
                        status="partial", evidence=[], holdings=[], gaps=["missing"],
                        claims=[Claim(id="c", text="business", assessment="supported",
                                      evidence_ids=["missing"], limitations=[])])


def test_historical_subset_preserves_weight_without_normalizing():
    data = HoldingsDisclosure(etf_symbol="512480", as_of=date(2026, 3, 31),
                              published_date=date(2026, 4, 22), evidence_id="q1",
                              coverage="other_subset",
                              holdings=[{"symbol": "688012", "nav_weight_pct": "4.29"}])
    assert str(data.holdings[0].nav_weight_pct) == "4.29"
    with pytest.raises(ValidationError):
        HoldingsDisclosure.model_validate({**data.model_dump(), "published_date": "2026-01-01"})


def test_validation_errors_cannot_be_automatically_retried():
    with pytest.raises(ValidationError):
        ContractError(code="VALIDATION_ERROR", message="invalid", retryable=True,
                      retry_after_seconds=5)


def test_execution_missing_inputs_cannot_return_quantity():
    from backend.policy_capital_contract import ExecutionPreview
    with pytest.raises(ValidationError):
        ExecutionPreview(status="blocked", quantity=200, estimated_cost="100",
                         remaining_cash="0", gaps=["fee unknown"], evidence_package_id="p")


def test_completed_job_requires_result_and_failed_requires_error():
    from backend.policy_capital_contract import ResearchJob
    with pytest.raises(ValidationError):
        ResearchJob(job_id="j", status="succeeded", result=None, error=None)
