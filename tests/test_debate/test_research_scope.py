from datetime import date

import pytest
from pydantic import ValidationError

from src.debate.research_scope import HorizonOpinion, scope_prompt


def test_scope_requires_conditions_and_explicit_period():
    opinion = dict(horizon="short", status="insufficient", direction=None,
                   thesis="缺少日线", assumptions=["取得完整日线"], invalidation=["报价更新"],
                   review_on="2026-10-07", review_trigger="开市取得行情", evidence=["9月30日报价"],
                   limitations="单源报价")
    assert HorizonOpinion(**opinion).direction is None
    with pytest.raises(ValidationError):
        HorizonOpinion(**{**opinion, "assumptions": [" "]})
    with pytest.raises(ValidationError):
        HorizonOpinion(**{**opinion, "horizon": "mixed"})
    prompt = scope_prompt(date(2026, 10, 6))
    assert all(x in prompt for x in ("2026-10-06", "short", "medium", "long", "发行价", "半年"))
