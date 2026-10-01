export interface DebateRequestState {
  sessionId: string | null;
  running: boolean;
}

export type DebateRequestAction =
  | { type: "start" }
  | { type: "succeeded"; sessionId: string }
  | { type: "failed" };

export interface DebatePollDecision {
  nextCount: number;
  continuePolling: boolean;
  timedOut: boolean;
}

export const INITIAL_DEBATE_REQUEST_STATE: DebateRequestState = {
  sessionId: null,
  running: false,
};

export const DEBATE_FAILURE_MESSAGE =
  "本次分析失败，已隐藏上次结果；请检查数据状态后重试。";

export const DEBATE_TIMEOUT_MESSAGE =
  "本次分析尚未完成，已停止等待；未生成新的投资结论。";

export function debateRequestReducer(
  state: DebateRequestState,
  action: DebateRequestAction,
): DebateRequestState {
  switch (action.type) {
    case "start":
      return { sessionId: null, running: true };
    case "succeeded":
      return { sessionId: action.sessionId, running: false };
    case "failed":
      return INITIAL_DEBATE_REQUEST_STATE;
    default:
      return state;
  }
}

export function advanceDebatePoll(
  currentCount: number,
  hasResult: boolean,
  maxPolls: number,
): DebatePollDecision {
  if (hasResult) {
    return {
      nextCount: currentCount,
      continuePolling: false,
      timedOut: false,
    };
  }

  const nextCount = currentCount + 1;
  const timedOut = nextCount >= maxPolls;
  return {
    nextCount,
    continuePolling: !timedOut,
    timedOut,
  };
}
