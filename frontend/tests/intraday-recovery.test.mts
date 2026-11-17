import test from "node:test";
import assert from "node:assert/strict";
import { IntradayUnavailableError, requireIntradayDisplay, latestMinuteSession, automaticPriceWindow } from "../lib/intraday-recovery.ts";
import { parseFiveDay, requireFiveDayDisplay } from "../lib/five-day-display.ts";
import type { IntradayBattlefield } from "../lib/types/stock.ts";
const now = Date.parse("2026-10-27T23:00:00+08:00");
const five = () => parseFiveDay({symbol: "002885", source: "tencent", price_basis: "unverified_raw", verification: "single_source",
  status: "partial", fetched_at: "2026-10-27T22:00:00+08:00", days: ["2026-10-26", "2026-10-27"],
  points: [{timestamp: "2026-10-26T15:00:00+08:00", close: 20.93}, {timestamp: "2026-10-27T09:30:00+08:00", close: 21.17},
    {timestamp: "2026-10-27T15:00:00+08:00", close: 20.10}], incomplete_days: ["2026-10-27"], missing_days: [], error_code: null}, "002885");

test("empty 200 becomes error with latest diagnostics; valid same-code data remains a success", () => {
  const value = {symbol: "002885", usable: false, price_points: [], source_diagnostics: []} as unknown as IntradayBattlefield;
  assert.throws(() => requireIntradayDisplay(value, "002885"), (e: unknown) => e instanceof IntradayUnavailableError && e.data === value);
  assert.throws(() => requireIntradayDisplay(value, "300750"));
  const valid = {...value, usable: true, price_points: [{close: 20.1}] } as IntradayBattlefield;
  assert.equal(requireIntradayDisplay(valid, "002885"), valid);
});

test("fallback slices actual latest session without inventing OHLC or cumulative volume", () => {
  const session = latestMinuteSession(five(), "002885", now)!;
  assert.equal(session.day, "2026-10-27"); assert.equal(session.isToday, true);
  assert.equal(session.points.length, 2); assert.equal(session.points[1].close, 20.1);
  assert.deepEqual(Object.keys(session.points[0]).sort(), ["close", "timestamp"]);
  assert.equal(session.incomplete, true);
  assert.equal(latestMinuteSession(five(), "300750", now), null);
});

test("historical fallback is dated and not called today; future latest session is rejected", () => {
  assert.equal(latestMinuteSession(five(), "002885", now + 86400000)!.isToday, false);
  assert.equal(latestMinuteSession(five(), "002885", Date.parse("2026-10-27T09:00:00+08:00")), null);
  assert.equal(latestMinuteSession(undefined, "002885", now), null);
});

test("default falls back to daily only after both minute paths fail, never overriding an explicit tab", () => {
  assert.equal(automaticPriceWindow(null, false, false, false), "intraday");
  assert.equal(automaticPriceWindow(null, true, true, false), "intraday");
  assert.equal(automaticPriceWindow(null, true, false, true), "intraday");
  assert.equal(automaticPriceWindow(null, true, false, false), "daily");
  assert.equal(automaticPriceWindow("intraday", true, false, false), "intraday");
  assert.equal(automaticPriceWindow("five-day", true, false, false), "five-day");
  assert.equal(automaticPriceWindow("daily", false, false, true), "daily");
});

test("empty and failed five-day refreshes are errors so query cache retains last success", () => {
  assert.equal(requireFiveDayDisplay(five()).status, "partial");
  for (const status of ["empty", "failed"] as const)
    assert.throws(() => requireFiveDayDisplay({...five(), status, points: [], days: []}));
});
