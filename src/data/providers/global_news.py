"""Bounded latest-feed samples from existing public Sina/Eastmoney channels."""
from __future__ import annotations

import html
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pandas as pd

from src.data.providers.news import SinaNewsSource, _default_sina_fetcher


def publication_time(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        dt = datetime.fromisoformat(value.strip())
        zone = ZoneInfo("Asia/Shanghai")
        dt = dt.replace(tzinfo=zone) if dt.tzinfo is None else dt.astimezone(zone)
        return dt.isoformat() if dt <= datetime.now(zone) else None
    except ValueError:
        return None


def text(value: object) -> str:
    return html.unescape(re.sub(r"<[^>]*>", "", value)).strip() if isinstance(value, str) else ""


def fetch_sina_hot_news() -> pd.DataFrame:
    payload = _default_sina_fetcher(page=1, page_size=100)
    rows, _ = SinaNewsSource._feed(payload)  # noqa: SLF001 — reuse validated feed schema
    return pd.DataFrame([
        {"title": text(row.get("rich_text")), "date": publication_time(row.get("create_time")),
         "source": "新浪财经", "url": text(row.get("docurl"))}
        for row in rows[:100]
    ])


def fetch_eastmoney_hot_news() -> pd.DataFrame:
    # Same endpoint/fields as AKShare stock_info_global_em, with an explicit timeout.
    response = httpx.get(
        "https://np-weblist.eastmoney.com/comm/web/getFastNewsList",
        params={"client": "web", "biz": "web_724", "fastColumn": "102",
                "sortEnd": "", "pageSize": "200", "req_trace": "1710315450384"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=10.0,
    )
    response.raise_for_status()
    rows = response.json()["data"]["fastNewsList"]
    if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Invalid Eastmoney news collection")
    return pd.DataFrame([
        {"title": text(row.get("title")) or text(row.get("summary")),
         "date": publication_time(row.get("showTime")), "source": "东方财富",
         "url": f"https://finance.eastmoney.com/a/{row['code']}.html"
         if re.fullmatch(r"\d+", str(row.get("code", ""))) else ""}
        for row in rows[:100]
    ])
