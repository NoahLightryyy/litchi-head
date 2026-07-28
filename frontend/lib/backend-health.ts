export type BackendState = "checking" | "connected" | "degraded" | "disconnected";

export type DiagnoseStatus = "healthy" | "degraded" | "healthy_with_warnings";

export interface BackendClassification {
  state: Exclude<BackendState, "checking">;
  message: string | null;
}

export const DIAGNOSTICS_UNAVAILABLE_MESSAGE = "后端已连接，诊断信息暂不可用";

export function classifyBackendProbe(
  healthOk: boolean,
  diagnoseStatus: DiagnoseStatus | null,
): BackendClassification {
  if (!healthOk) {
    return { state: "disconnected", message: null };
  }

  if (diagnoseStatus === "healthy") {
    return { state: "connected", message: null };
  }

  if (diagnoseStatus === null) {
    return {
      state: "degraded",
      message: DIAGNOSTICS_UNAVAILABLE_MESSAGE,
    };
  }

  return { state: "degraded", message: null };
}
