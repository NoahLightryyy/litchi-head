import assert from "node:assert/strict";
import test from "node:test";

import {
  DIAGNOSTICS_UNAVAILABLE_MESSAGE,
  classifyBackendProbe,
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
