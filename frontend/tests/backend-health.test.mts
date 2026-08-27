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
          last_error: null,
        },
        news: {
          failures: 0,
          last_error: null,
        },
        __summary__: {
          total_failures: 0,
          failing_endpoints: 0,
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
          last_error: "timeout",
        },
        __summary__: {
          total_failures: 2,
          failing_endpoints: 1,
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
