"""Preserve publication timestamps discarded by AKShare's Caixin projection."""
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd


def publication_time(value: object) -> str | None:
    """Caixin time is Unix seconds; invalid or missing values stay unknown."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None
    try:
        return datetime.fromtimestamp(value, ZoneInfo("Asia/Shanghai")).isoformat()
    except (ValueError, OverflowError, OSError):
        return None


def fetch_caixin_news() -> pd.DataFrame:
    """Use the same public endpoint, retaining summary text and original time."""
    response = httpx.get(
        "https://cxdata.caixin.com/api/dataplus/sjtPc/news",
        params={"pageNum": "1", "pageSize": "100", "showLabels": "true"},
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://cxdata.caixin.com/index/newsTab?tab=latest"},
        timeout=10.0,
    )
    response.raise_for_status()
    rows = response.json()["data"]["data"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid Caixin news collection")
    return pd.DataFrame([
        {"summary": row.get("summary") or row.get("title"), "url": row.get("url"),
         "date": publication_time(row.get("time"))}
        for row in rows
    ])
