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


def epoch_time(value: object) -> str | None:
    try:
        return publication_time(datetime.fromtimestamp(float(str(value)),
                                ZoneInfo("Asia/Shanghai")).isoformat())
    except (ValueError, TypeError, OverflowError, OSError):
        return None


def _get_json(url: str, params: dict[str, str]) -> dict:
    response = httpx.get(url, params=params, timeout=10,
                         headers={"User-Agent": "Mozilla/5.0", "Referer": url})
    response.raise_for_status()
    return response.json()


def fetch_futu_hot_news() -> pd.DataFrame:
    payload = _get_json("https://news.futunn.com/news-site-api/main/get-flash-list",
                        {"pageSize": "100"})
    rows = payload["data"]["data"]["news"]
    return pd.DataFrame([
        {"title": text(row.get("title")) or text(row.get("content")),
         "content": text(row.get("content")), "date": epoch_time(row.get("time")),
         "source": "富途财经", "url": text(row.get("detailUrl"))} for row in rows[:100]
    ])


def fetch_ths_hot_news() -> pd.DataFrame:
    payload = _get_json("https://news.10jqka.com.cn/tapp/news/push/stock",
                        {"page": "1", "tag": "", "track": "website"})
    rows = payload["data"]["list"]
    return pd.DataFrame([
        {"title": text(row.get("title")) or text(row.get("digest")),
         "content": text(row.get("digest")), "date": epoch_time(row.get("rtime")),
         "source": "同花顺财经", "url": text(row.get("url"))} for row in rows[:100]
    ])


def fetch_cls_hot_news() -> pd.DataFrame:
    import hashlib
    import time
    from urllib.parse import urlencode

    # Public web request signature; rn=100 returns an empty collection upstream.
    params = {"app": "CailianpressWeb", "category": "", "last_time": str(int(time.time())),
              "os": "web", "refresh_type": "1", "rn": "20", "sv": "8.4.6"}
    params["sign"] = hashlib.md5(
        hashlib.sha1(urlencode(params).encode()).hexdigest().encode()).hexdigest()
    payload = _get_json("https://www.cls.cn/v1/roll/get_roll_list", params)
    if payload.get("errno") != 0:
        raise ValueError("CLS feed error")
    rows = payload["data"]["roll_data"]
    return pd.DataFrame([
        {"title": text(row.get("title")) or text(row.get("content")),
         "content": text(row.get("content")), "date": epoch_time(row.get("ctime")),
         "source": "财联社", "url": f"https://www.cls.cn/detail/{row['id']}"
         if re.fullmatch(r"\d+", str(row.get("id", ""))) else ""} for row in rows[:100]
    ])
