"""Deterministic ETF keyword matching over catalog names, never invented identities."""

from __future__ import annotations

import re
import unicodedata
from collections import Counter

_TOKENS = re.compile(r"[a-z0-9]+|[\u3400-\u9fff]+")
_HAN = re.compile(r"[\u3400-\u9fff]+")
_ETF_WORDS = re.compile(r"etf|基金公司|基金管理|基金")


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _han_fragments_match(query: str, name: str) -> bool:
    """Cover each query run with name fragments of >=2 Han characters, in any order.

    This is not edit distance or character-bag matching: 半导体 + 广发 may
    match 半导体设备ETF广发, but 半广 + 导发 + 体 may not.
    The DP is bounded by the route's 80-character query limit.
    """
    reachable = [False] * (len(query) + 1)
    reachable[0] = True
    for end in range(2, len(query) + 1):
        reachable[end] = any(
            reachable[start] and query[start:end] in name for start in range(end - 1)
        )
    return reachable[-1]


def search_match_rank(query: str, *, code: str, name: str, kind: str) -> int | None:
    """Exact code/name first, legacy substring next, ETF keyword conjunction last."""
    query, name = _normalise(query), _normalise(name)
    if not query:
        return None
    if query == code.casefold():
        return 0
    if query == name:
        return 1
    if query in code.casefold() or query in name:
        return 2
    if kind != "etf":
        return None

    has_category = bool(_ETF_WORDS.search(query))
    # Category words and the grammatical 的 are not part of theme/manager names.
    meaningful = _ETF_WORDS.sub(" ", query).replace("的", " ")
    terms = _TOKENS.findall(meaningful)
    if not terms:
        return 3 if has_category else None

    # Do not match repeated/overlapping query characters against the same letters.
    han_query = "".join(term for term in terms if _HAN.fullmatch(term))
    if Counter(han_query) - Counter(name):
        return None
    ascii_terms = set(re.findall(r"[a-z0-9]+", _ETF_WORDS.sub(" ", name))) | {code}
    for term in terms:
        if _HAN.fullmatch(term):
            if not _han_fragments_match(term, name):
                return None
        elif term not in ascii_terms:
            return None
    return 3
