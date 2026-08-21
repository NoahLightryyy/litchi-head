import assert from "node:assert/strict";
import test from "node:test";

import {
  describeIntradayDiagnostics,
  describeIntradayRequestError,
  describeIntradaySourceState,
  formatShanghaiChartTime,
  resolveIntradayPanelMode,
  toIntradayLineData,
} from "../lib/intraday-source-state.ts";
import { parseIntradayBattlefield } from "../lib/intraday-contract.ts";
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
      detail: "腾讯 + 东方财富 · 数据时间 10:42",
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

test("request errors distinguish network, server, rate limit and contract failures", () => {
  assert.equal(
    describeIntradayRequestError({ code: "NETWORK_ERROR", status: 0 }).title,
    "分时接口连接失败",
  );
  assert.equal(
    describeIntradayRequestError({ code: "RATE_LIMITED", status: 429 }).title,
    "分时请求过于频繁",
  );
  assert.equal(
    describeIntradayRequestError({ code: "UNKNOWN", status: 503 }).title,
    "分时服务暂不可用",
  );
  assert.equal(
    describeIntradayRequestError({ name: "IntradayContractError" }).title,
    "分时接口版本不兼容",
  );
});

test("panel mode keeps loading, network failure, unavailable evidence and usable evidence distinct", () => {
  assert.equal(
    resolveIntradayPanelMode({ data: undefined, isLoading: true, isError: false }),
    "loading",
  );
  assert.equal(
    resolveIntradayPanelMode({ data: undefined, isLoading: false, isError: true }),
    "network_error",
  );
  assert.equal(
    resolveIntradayPanelMode({
      data: battlefield({ usable: false, verification_status: "unavailable" }),
      isLoading: false,
      isError: false,
    }),
    "unavailable",
  );
  assert.equal(
    resolveIntradayPanelMode({
      data: battlefield({
        price_points: [
          {
            code: "000001",
            timestamp: "2026-08-12T10:42:00+08:00",
            close: 11.42,
            cumulative_volume: 120_000,
            cumulative_amount: 1_370_400,
            state: "provisional",
          },
        ],
      }),
      isLoading: false,
      isError: false,
    }),
    "usable",
  );
  assert.equal(
    resolveIntradayPanelMode({
      data: battlefield({
        price_points: [
          {
            code: "000001",
            timestamp: AS_OF,
            close: 11.42,
            cumulative_volume: 120_000,
            cumulative_amount: 1_370_400,
            state: "provisional",
          },
        ],
      }),
      isLoading: false,
      isError: true,
    }),
    "stale_error",
  );
  assert.equal(
    resolveIntradayPanelMode({
      data: battlefield({ usable: false, verification_status: "unavailable" }),
      isLoading: false,
      isError: true,
    }),
    "unavailable",
  );
});

test("line data contains only timestamp and close price and ignores malformed points", () => {
  assert.deepEqual(
    toIntradayLineData([
      {
        code: "000001",
        timestamp: "2026-08-12T09:30:00+08:00",
        close: 11.31,
        cumulative_volume: 10_000,
        cumulative_amount: 113_100,
        state: "final",
      },
      {
        code: "000001",
        timestamp: "invalid-time",
        close: 99.99,
        cumulative_volume: 99_999,
        cumulative_amount: 999_999,
        state: "provisional",
      },
      {
        code: "000001",
        timestamp: "2026-08-12T10:42:00+08:00",
        close: 11.42,
        cumulative_volume: 120_000,
        cumulative_amount: 1_370_400,
        state: "provisional",
      },
    ]),
    [
      { time: 1_786_498_200, value: 11.31 },
      { time: 1_786_502_520, value: 11.42 },
    ],
  );
});

test("chart time labels use the Shanghai trading clock instead of UTC", () => {
  assert.equal(formatShanghaiChartTime(1_786_498_200), "09:30");
  assert.equal(formatShanghaiChartTime(1_786_502_520), "10:42");
});

test("API timestamps are converted from UTC and timezone-less values are rejected", () => {
  assert.equal(
    describeIntradayDiagnostics(
      battlefield({
        source_diagnostics: [
          {
            ...battlefield().source_diagnostics[0],
            fetched_at: "2026-08-12T02:42:00Z",
          },
          {
            ...battlefield().source_diagnostics[1],
            fetched_at: "2026-08-12T10:42:00",
          },
        ],
      }),
    )[0].fetchedTime,
    "10:42",
  );
  assert.equal(
    describeIntradayDiagnostics(
      battlefield({
        source_diagnostics: [
          {
            ...battlefield().source_diagnostics[0],
            fetched_at: "2026-08-12T10:42:00",
          },
        ],
      }),
    )[0].fetchedTime,
    "时间格式无时区",
  );
});

test("line data is sorted, deduplicated by second and keeps the latest duplicate", () => {
  const base = battlefield().price_points;
  assert.deepEqual(
    toIntradayLineData([
      {
        code: "000001",
        timestamp: "2026-08-12T10:42:00.900+08:00",
        close: 11.43,
        cumulative_volume: 2,
        cumulative_amount: 2,
        state: "provisional",
      },
      {
        code: "000001",
        timestamp: "2026-08-12T09:30:00+08:00",
        close: 11.31,
        cumulative_volume: 1,
        cumulative_amount: 1,
        state: "final",
      },
      {
        code: "000001",
        timestamp: "2026-08-12T10:42:00.100+08:00",
        close: 11.42,
        cumulative_volume: 2,
        cumulative_amount: 2,
        state: "provisional",
      },
      ...base,
    ]),
    [
      { time: 1_786_498_200, value: 11.31 },
      { time: 1_786_502_520, value: 11.42 },
    ],
  );
});

test("runtime contract rejects the legacy backend envelope instead of crashing the panel", () => {
  const validBattlefield = battlefield({
    price_points: [
      {
        code: "000001",
        timestamp: AS_OF,
        close: 11.42,
        cumulative_volume: 1,
        cumulative_amount: 1,
        state: "provisional",
      },
    ],
  });
  assert.throws(
    () =>
      parseIntradayBattlefield({
        symbol: "000001",
        complete: false,
        collected_at: AS_OF,
        assessment: battlefield().assessment,
        source_diagnostics: [],
        bars: [],
        snapshot: null,
      }),
    /分时接口响应契约不兼容/,
  );
  assert.deepEqual(parseIntradayBattlefield(validBattlefield), validBattlefield);
  assert.throws(
    () =>
      parseIntradayBattlefield(
        battlefield({
          price_points: [
            {
              code: "000001",
              timestamp: "2026-08-12T10:42:00+08:00",
              close: 11.42,
              cumulative_volume: 1,
              cumulative_amount: 1,
              state: "provisional",
            },
            {
              code: "000001",
              timestamp: "2026-08-12T09:30:00+08:00",
              close: 11.31,
              cumulative_volume: 1,
              cumulative_amount: 1,
              state: "final",
            },
          ],
        }),
      ),
    /分时接口响应契约不兼容/,
  );
  assert.throws(
    () =>
      parseIntradayBattlefield(
        {
          ...validBattlefield,
          snapshot: {
            code: "000001",
            evidence_level: "L1",
            as_of: AS_OF,
            current_price: "bad" as unknown as number,
            current_bar_state: "provisional",
            session_vwap: 11.4,
            vwap_deviation_pct: 0.2,
            vwap_position: "above",
            opening_range_high: 11.5,
            opening_range_low: 11.2,
            cumulative_volume: 1,
            relative_volume: 1.1,
            relative_volume_sample_days: 20,
            attribution_supported: false,
            limitations: [],
          },
        },
      ),
    /分时接口响应契约不兼容/,
  );
  assert.throws(
    () =>
      parseIntradayBattlefield(
        battlefield({
          price_points: [
            {
              code: "600000",
              timestamp: AS_OF,
              close: 11.42,
              cumulative_volume: 1,
              cumulative_amount: 1,
              state: "provisional",
            },
          ],
        }),
      ),
    /分时接口响应契约不兼容/,
  );
  assert.throws(
    () =>
      parseIntradayBattlefield(
        { ...validBattlefield, as_of: "2026-08-12T10:42:00" },
      ),
    /分时接口响应契约不兼容/,
  );
});

test("diagnostic disclosure uses API facts and never infers blame", () => {
  assert.deepEqual(describeIntradayDiagnostics(battlefield()), [
    {
      sourceId: "direct-tencent-intraday",
      sourceName: "腾讯",
      statusLabel: "数据可用",
      fetchedTime: "10:42",
      checkpointCount: 240,
      errorMessage: null,
    },
    {
      sourceId: "direct-eastmoney-intraday",
      sourceName: "东方财富",
      statusLabel: "请求失败",
      fetchedTime: "10:42",
      checkpointCount: 0,
      errorMessage: "timeout",
    },
  ]);
});
