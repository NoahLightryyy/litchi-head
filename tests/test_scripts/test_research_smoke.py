"""Scoring must reject plausible prose with an incorrect machine answer."""

from scripts.evaluate_research_smoke import score


def test_score_requires_correct_typed_answer() -> None:
    assert score('{"answer":220}', 220)
    assert score('{"answer":false}', False)
    assert not score('{"answer":180,"reason":"合计220元"}', 220)
    assert not score('{"answer":true,"reason":"不能买入"}', False)
    assert not score('{"answer":true}', 1)
    assert not score('{"answer":"false"}', False)
    assert not score('not json', False)
    assert not score('{"answer":NaN}', 220)
