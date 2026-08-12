import assert from "node:assert/strict";
import test from "node:test";

import {
  describeIntradaySourceState,
} from "../lib/intraday-source-state.ts";
import type { IntradayBattlefield } from "../lib/types/stock.ts";

const AS_OF = "2026-08-12T10:42:00+08:00";

function battlefield(
  overrides: Partial<IntradayBattlefield> = {},
): IntradayBattlefield {
  return {
    symbol: "000001",
    complete: false,
    usable: true,
    verification_status: "single_source",
    canonical_source_id: "direct-tencent-intraday",
    available_source_ids: ["direct-tencent-intraday"],
    failed_source_ids: ["direct-eastmoney-intraday"],
    as_of: AS_OF,
    collected_at: AS_OF,
    assessment: {
      capability: "intraday",
      complete: false,
      successful_upstream_ids: ["tencent"],
      successful_source_ids: ["direct-tencent-intraday"],
      failed_source_ids: ["direct-eastmoney-intraday"],
      discovery_only_source_ids: [],
      unusable_source_ids: ["direct-eastmoney-intraday"],
      missing_required_upstream_ids: ["eastmoney"],
      missing_independent_upstreams: 1,
    },
    source_diagnostics: [
      {
        source_id: "direct-tencent-intraday",
        source_name: "腾讯",
        upstream_id: "tencent",
        status: "success_data",
        fetched_at: AS_OF,
        error_code: null,
        error_message: null,
        checkpoint_count: 240,
        latest_timestamp: AS_OF,
      },
      {
        source_id: "direct-eastmoney-intraday",
        source_name: "东方财富",
        upstream_id: "eastmoney",
        status: "failed",
        fetched_at: AS_OF,
        error_code: "upstream_request_failed",
        error_message: "timeout",
        checkpoint_count: 0,
        latest_timestamp: null,
      },
    ],
    bars: [],
    price_points: [],
    snapshot: null,
    ...overrides,
  };
}

test("single-source state discloses the diagnostic source and lack of cross-verification", () => {
  assert.deepEqual(describeIntradaySourceState(battlefield()), {
    label: "单一数据源 · 腾讯",
    detail: "未交叉验证 · 数据时间 10:42",
    tone: "warning",
  });
});

test("conflict state names the diagnostic canonical source and says sources disagree", () => {
  assert.deepEqual(
    describeIntradaySourceState(
      battlefield({
        verification_status: "source_conflict",
        available_source_ids: [
          "direct-eastmoney-intraday",
          "direct-tencent-intraday",
        ],
        failed_source_ids: [],
        canonical_source_id: "direct-eastmoney-intraday",
        source_diagnostics: [
          {
            source_id: "direct-eastmoney-intraday",
            source_name: "东方财富",
            upstream_id: "eastmoney",
            status: "conflicted",
            fetched_at: AS_OF,
            error_code: "intraday_price_conflict",
            error_message: "price mismatch",
            checkpoint_count: 240,
            latest_timestamp: AS_OF,
          },
          {
            source_id: "direct-tencent-intraday",
            source_name: "腾讯",
            upstream_id: "tencent",
            status: "conflicted",
            fetched_at: AS_OF,
            error_code: "intraday_price_conflict",
            error_message: "price mismatch",
            checkpoint_count: 240,
            latest_timestamp: AS_OF,
          },
        ],
      }),
    ),
    {
      label: "数据源存在分歧 · 当前采用东方财富",
      detail: "数据源之间存在分歧 · 数据时间 10:42",
      tone: "conflict",
    },
  );
});

test("multi-source verification is explicitly identified", () => {
  assert.deepEqual(
    describeIntradaySourceState(
      battlefield({
        complete: true,
        verification_status: "multi_source_verified",
        available_source_ids: [
          "direct-eastmoney-intraday",
          "direct-tencent-intraday",
        ],
        failed_source_ids: [],
      }),
    ),
    {
      label: "多源交叉验证通过",
      detail: "数据时间 10:42",
      tone: "verified",
    },
  );
});

test("unavailable and incomplete diagnostics do not invent a source or data time", () => {
  assert.deepEqual(
    describeIntradaySourceState(
      battlefield({
        usable: false,
        verification_status: "unavailable",
        canonical_source_id: null,
        available_source_ids: [],
        as_of: null,
      }),
    ),
    {
      label: "分时数据暂不可用",
      detail: "暂无通过本地校验的数据源",
      tone: "unavailable",
    },
  );

  assert.deepEqual(
    describeIntradaySourceState(
      battlefield({
        canonical_source_id: "diagnostic-missing-source",
        as_of: null,
      }),
    ),
    {
      label: "单一数据源 · 来源待确认",
      detail: "未交叉验证 · 数据时间暂不可用",
      tone: "warning",
    },
  );
});
