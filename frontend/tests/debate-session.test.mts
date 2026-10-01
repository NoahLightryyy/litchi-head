import assert from "node:assert/strict";
import test from "node:test";

import {
  DEBATE_FAILURE_MESSAGE,
  DEBATE_TIMEOUT_MESSAGE,
  INITIAL_DEBATE_REQUEST_STATE,
  advanceDebatePoll,
  debateRequestReducer,
} from "../lib/debate-session.ts";

test("新辩论开始时立即解除旧 session，失败后不会恢复旧结果", () => {
  const previousSuccess = {
    sessionId: "deb_previous",
    running: false,
  };

  const starting = debateRequestReducer(previousSuccess, { type: "start" });
  assert.deepEqual(starting, { sessionId: null, running: true });

  const failed = debateRequestReducer(starting, { type: "failed" });
  assert.deepEqual(failed, INITIAL_DEBATE_REQUEST_STATE);
});

test("只有本次成功返回的 session 才能进入结果查询", () => {
  const starting = debateRequestReducer(INITIAL_DEBATE_REQUEST_STATE, {
    type: "start",
  });
  const succeeded = debateRequestReducer(starting, {
    type: "succeeded",
    sessionId: "deb_current",
  });

  assert.deepEqual(succeeded, {
    sessionId: "deb_current",
    running: false,
  });
});

test("结果出现后立即停止轮询且不报告超时", () => {
  assert.deepEqual(advanceDebatePoll(12, true, 60), {
    nextCount: 12,
    continuePolling: false,
    timedOut: false,
  });
});

test("第 60 次仍无结果时停止轮询并报告超时", () => {
  assert.deepEqual(advanceDebatePoll(59, false, 60), {
    nextCount: 60,
    continuePolling: false,
    timedOut: true,
  });
});

test("失败与超时文案使用已确认的安全提示", () => {
  assert.equal(
    DEBATE_FAILURE_MESSAGE,
    "本次分析失败，已隐藏上次结果；请检查数据状态后重试。",
  );
  assert.equal(
    DEBATE_TIMEOUT_MESSAGE,
    "本次分析尚未完成，已停止等待；未生成新的投资结论。",
  );
});
