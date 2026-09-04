"""Read-only, reproducible Eastmoney snapshot/category audit (does not enable routes).

Run: python -m scripts.diagnose_board_snapshots --output report.json
"""
from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from src.data.providers.eastmoney_boards import (
    SHANGHAI,
    BoardKind,
    EastmoneyBoardSnapshots,
)

CATALOG_URL = "https://quote.eastmoney.com/center/api/sidemenu_new.json"


class RecordingTransport(httpx.BaseTransport):
    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.pages: list[dict[str, Any]] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        started = time.monotonic()
        response = self.client.send(request)
        response.raise_for_status()
        payload = response.json()
        data = payload.get("data") or {}
        rows = data.get("diff") or []
        self.pages.append({
            "url": str(request.url), "seconds": round(time.monotonic() - started, 4),
            "sha256": hashlib.sha256(response.content).hexdigest(),
            "rc": payload.get("rc"), "total": data.get("total"), "count": len(rows),
            "codes": [row.get("f12") for row in rows],
            "markets": sorted({row.get("f13") for row in rows}),
        })
        return response


def diagnose() -> dict[str, Any]:
    report: dict[str, Any] = {"observed_at": datetime.now(SHANGHAI).isoformat()}
    with httpx.Client(timeout=6) as client:
        response = client.get(CATALOG_URL)
        response.raise_for_status()
        catalog = response.json()["bklist"]
        report["catalog"] = {
            "url": CATALOG_URL, "sha256": hashlib.sha256(response.content).hexdigest(),
            "total": len(catalog), "types": dict(Counter(row["type"] for row in catalog)),
            "industry_levels": dict(Counter(row["flag"] for row in catalog if row["type"] == 2)),
        }
        transport = RecordingTransport(client)
        service = EastmoneyBoardSnapshots(transport=transport)
        categories: dict[str, Any] = {}
        for kind, category in (("industry", 2), ("concept", 3)):
            board_kind: BoardKind = "industry" if kind == "industry" else "concept"
            started = time.monotonic()
            snapshot = service.fetch(board_kind)
            cold_seconds = time.monotonic() - started
            page_count = len(transport.pages)
            started = time.monotonic()
            warm = service.fetch(board_kind)
            warm_seconds = time.monotonic() - started
            assert warm.cached and len(transport.pages) == page_count
            expected = {row["code"]: row for row in catalog if row["type"] == category}
            actual = {quote.code: quote for quote in snapshot.quotes}
            extra = sorted(actual.keys() - expected.keys())
            missing = sorted(expected.keys() - actual.keys())
            name_mismatches = [code for code, quote in actual.items()
                               if code in expected and quote.name != expected[code]["name"]]
            categories[kind] = {
                "count": len(snapshot.quotes), "unique_ids": len(actual),
                "cold_seconds": round(cold_seconds, 4), "warm_seconds": round(warm_seconds, 6),
                "source": snapshot.source, "possibly_delayed": snapshot.possibly_delayed,
                "official_count": len(expected), "extra_ids": extra,
                "missing_directory_entries": [expected[code] for code in missing],
                "name_mismatches": name_mismatches,
                "levels": dict(Counter(
                    expected[code]["flag"] for code in actual if code in expected
                )),
                "as_of_min": min(quote.as_of for quote in snapshot.quotes).isoformat(),
                "as_of_max": max(quote.as_of for quote in snapshot.quotes).isoformat(),
                "samples": [
                    {**quote.model_dump(mode="json"), "official": expected.get(quote.code)}
                    for quote in snapshot.quotes[:5]
                ],
                "all_ids": sorted(actual),
            }
            assert not extra and not name_mismatches, "quote/category identity mismatch"
        report["categories"] = categories
        report["cross_category_overlap"] = sorted(
            set(categories["industry"]["all_ids"]) & set(categories["concept"]["all_ids"]),
        )
        report["pages"] = transport.pages
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diagnose()
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"Saved category and pagination evidence to {args.output}")


if __name__ == "__main__":
    main()
