"""Recognize explicit provider balance failures, including persisted legacy errors."""

import re


def is_balance_error(error: object) -> bool:
    """Never infer a billing problem from a missing opinion or a number alone."""
    return bool(re.search(
        r"LLM_INSUFFICIENT_BALANCE|insufficient_balance_error|\binsufficient\s+balance\b",
        str(error or ""), re.IGNORECASE,
    ))
