export type BackendState = "checking" | "connected" | "degraded" | "disconnected";

export type DiagnoseStatus = "healthy" | "degraded" | "healthy_with_warnings";

export interface DiagnoseCheck {
  status: string;
  error?: string;
  message?: string;
}

export interface DiagnoseResult {
  status: DiagnoseStatus;
  checks: Record<string, DiagnoseCheck>;
}

export interface BackendClassification {
  state: Exclude<BackendState, "checking">;
  message: string | null;
}

export const DIAGNOSTICS_UNAVAILABLE_MESSAGE = "后端已连接，诊断信息暂不可用";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0;
}

/** Converts the documented /api/health/data-source payload into the UI contract. */
export function normalizeDataSourceDiagnostics(value: unknown): DiagnoseResult | null {
  if (!isRecord(value) || !isRecord(value.stats)) return null;

  const summary = value.stats.__summary__;
  if (
    !isRecord(summary) ||
    !isNonNegativeInteger(summary.total_failures) ||
    !isNonNegativeInteger(summary.failing_endpoints)
  ) {
    return null;
  }

  const checks: Record<string, DiagnoseCheck> = {};
  for (const [name, rawCheck] of Object.entries(value.stats)) {
    if (name === "__summary__") continue;
    if (!isRecord(rawCheck) || !isNonNegativeInteger(rawCheck.failures)) {
      return null;
    }

    if (rawCheck.failures > 0) {
      checks[name] = {
        status: "fail",
        ...(typeof rawCheck.last_error === "string"
          ? { error: rawCheck.last_error }
          : {}),
      };
    } else {
      checks[name] = { status: "pass" };
    }
  }

  const degraded =
    value.status !== "ok" ||
    summary.total_failures > 0 ||
    summary.failing_endpoints > 0;
  return {
    status: degraded ? "degraded" : "healthy",
    checks,
  };
}

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
