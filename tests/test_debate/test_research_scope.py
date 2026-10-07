from datetime import date

import pytest
from pydantic import ValidationError

from src.debate.research_scope import HorizonOpinion, scope_prompt


def test_scope_requires_conditions_and_explicit_period():
    opinion = dict(
        horizon="short",
        status="insufficient",
        direction=None,
        thesis="缺少日线",
        assumptions=["取得完整日线"],
        invalidation=["报价更新"],
        review_on="2026-10-07",
        review_trigger="开市取得行情",
        evidence=["9月30日报价"],
        limitations="单源报价",
    )
    assert HorizonOpinion(**opinion).direction is None
    with pytest.raises(ValidationError):
        HorizonOpinion(**{**opinion, "assumptions": [" "]})
    with pytest.raises(ValidationError):
        HorizonOpinion(**{**opinion, "horizon": "mixed"})
    prompt = scope_prompt(date(2026, 10, 6))
    assert all(x in prompt for x in ("2026-10-06", "short", "medium", "long", "发行价", "半年"))


def test_scope_survives_json_history_round_trip():
    from datetime import UTC, datetime

    from src.debate.models import AgentAnalysis

    opinion = HorizonOpinion(
        horizon="long",
        status="supported",
        direction="Neutral",
        thesis="长期观察",
        assumptions=["现金流覆盖投入"],
        invalidation=["现金流持续下降"],
        review_on=date(2027, 1, 1),
        review_trigger="新财报",
        evidence=["2026中报"],
        limitations="单源",
    )
    row = AgentAnalysis(
        agent_name="master.a",
        skill_id="a",
        skill_name="A",
        rating="中性",
        score=50,
        summary="三周期研究",
        analysis="研究原文",
        horizons=[opinion],
        research_generated_at=datetime(2026, 10, 6, tzinfo=UTC),
    )
    restored = AgentAnalysis.model_validate_json(row.model_dump_json())
    assert restored.horizons == [opinion]
    assert restored.research_generated_at == row.research_generated_at
    assert (
        AgentAnalysis.model_validate(
            {
                k: v
                for k, v in row.model_dump().items()
                if k not in {"horizons", "research_generated_at"}
            }
        ).horizons
        == []
    )
