"""Related-material interpretation is explicit, cited, and reusable without generation."""

import pytest
from pydantic import ValidationError

from backend.related_interpretation_contract import (
    RelatedInference,
    RelatedInterpretationDraft,
    RelatedInterpretationRequest,
)


def test_request_reuses_success_by_default_and_forbids_client_materials():
    assert RelatedInterpretationRequest().refresh is False
    assert RelatedInterpretationRequest(refresh=True).refresh is True
    with pytest.raises(ValidationError):
        RelatedInterpretationRequest.model_validate({"articles": ["client text"]})


def test_contract_allows_excluding_all_sources_without_inventing_an_event():
    result = RelatedInterpretationDraft(
        overview="现有运输材料与本标的关联较弱。", events=[],
        excluded_sources=[{"source_id": "news:1", "reason": "只有宽泛运输词匹配"}],
        limitations=["没有直接业务关联证据"],
    )
    assert result.events == []
    with pytest.raises(ValidationError):
        RelatedInference.model_validate({"text": "或影响需求", "basis": "reported"})
