import assert from "node:assert/strict";
import test from "node:test";

import {
  DIAGNOSTICS_UNAVAILABLE_MESSAGE,
  classifyBackendProbe,
  normalizeDataSourceDiagnostics,
} from "../lib/backend-health.ts";

test("健康检查失败时才判定后端未连接", () => {
  assert.deepEqual(classifyBackendProbe(false, null), {
    state: "disconnected",
    message: null,
  });
});

test("健康检查和完整诊断均正常时判定已连接", () => {
  assert.deepEqual(classifyBackendProbe(true, "healthy"), {
    state: "connected",
    message: null,
  });
});

test("健康检查成功但完整诊断降级时显示黄色状态", () => {
  assert.deepEqual(classifyBackendProbe(true, "healthy_with_warnings"), {
    state: "degraded",
    message: null,
  });
  assert.deepEqual(classifyBackendProbe(true, "degraded"), {
    state: "degraded",
    message: null,
  });
});

test("健康检查成功但诊断接口不可用时不能误报后端断开", () => {
  assert.deepEqual(classifyBackendProbe(true, null), {
    state: "degraded",
    message: DIAGNOSTICS_UNAVAILABLE_MESSAGE,
  });
  assert.equal(DIAGNOSTICS_UNAVAILABLE_MESSAGE, "后端已连接，诊断信息暂不可用");
});

test("将后端 data-source 健康统计转换为前端诊断契约", () => {
  assert.deepEqual(
    normalizeDataSourceDiagnostics({
      status: "ok",
      stats: {
        quotes: {
          failures: 0,
          current_status: "healthy",
          last_error: null,
        },
        news: {
          failures: 0,
          current_status: "healthy",
          last_error: null,
        },
        __summary__: {
          total_failures: 0,
          failing_endpoints: 0,
          empty_endpoints: 0,
        },
      },
    }),
    {
      status: "healthy",
      checks: {
        quotes: { status: "pass" },
        news: { status: "pass" },
      },
    },
  );
});

test("数据源存在失败时保留错误事实并判定降级", () => {
  assert.deepEqual(
    normalizeDataSourceDiagnostics({
      status: "ok",
      stats: {
        quotes: {
          failures: 2,
          current_status: "failed",
          last_error: "timeout",
        },
        __summary__: {
          total_failures: 2,
          failing_endpoints: 1,
          empty_endpoints: 0,
        },
      },
    }),
    {
      status: "degraded",
      checks: {
        quotes: { status: "fail", error: "timeout" },
      },
    },
  );
});

test("拒绝缺少汇总字段的未知诊断响应", () => {
  assert.equal(normalizeDataSourceDiagnostics({ status: "ok", stats: {} }), null);
  assert.equal(normalizeDataSourceDiagnostics(null), null);
});

test("恢复后保留历史失败统计但解除来源故障；空结果和未知状态不能误报健康", () => {
  const payload = (current_status: unknown, last_error: string | null = null) => ({
    status: "ok", stats: {
      sina: { failures: 12, current_status, last_error },
      __summary__: { total_failures: 12, failing_endpoints: 0, empty_endpoints: 0 },
    },
  });
  assert.deepEqual(normalizeDataSourceDiagnostics(payload("healthy")), {
    status: "healthy", checks: { sina: { status: "pass" } },
  });
  assert.deepEqual(normalizeDataSourceDiagnostics(payload("empty", "数据源返回空数据")), {
    status: "degraded", checks: { sina: { status: "warn", error: "数据源返回空数据" } },
  });
  for (const status of [undefined, "unknown", null, ["healthy"], {}]) {
    assert.equal(normalizeDataSourceDiagnostics(payload(status)), null);
  }
  const mixed = payload("healthy");
  assert.deepEqual(normalizeDataSourceDiagnostics({ ...mixed, status: "degraded", stats: {
    ...mixed.stats, eastmoney: { failures: 5, current_status: "failed", last_error: "数据源请求失败" },
    __summary__: { total_failures: 17, failing_endpoints: 1, empty_endpoints: 0 },
  } })?.checks, { sina: { status: "pass" }, eastmoney: { status: "fail", error: "数据源请求失败" } });
});
