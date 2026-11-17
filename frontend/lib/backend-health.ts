export type BackendState = "checking" | "connected" | "degraded" | "disconnected";

export type DiagnoseStatus = "healthy" | "degraded" | "healthy_with_warnings";

export interface DiagnoseCheck {
  status: string;
  error?: string;
  errorCode?: string;
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

/** Count unavailable capabilities separately from interchangeable failed sources. */
export function partitionDiagnostics(checks: Record<string, DiagnoseCheck>) {
  const entries = Object.entries(checks);
  // A successful backend index batch covers all three indices, not just one quote.
  const hasIndexFallback = entries.some(([name, check]) =>
    name.startsWith("market_index:") && check.status === "pass");
  const failures = entries.filter(([, check]) => check.status !== "pass");
  const redundant = ([name, check]: [string, DiagnoseCheck]) => hasIndexFallback &&
    name.startsWith("market_index:") && check.errorCode !== "index_quote_conflict";
  return {
    issues: failures.filter(entry => !redundant(entry)),
    backupFailures: failures.filter(redundant),
  };
}

export function backendStateLabel(state: BackendState, message: string | null): string {
  return {
    checking: "连接中",
    connected: "已连接",
    degraded: message ? "已连接 · 诊断暂缺" : "已连接 · 数据受限",
    disconnected: "未连接",
  }[state];
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && typeof value === "number" && value >= 0;
}

/** Converts the documented /api/health/data-source payload into the UI contract. */
export function normalizeDataSourceDiagnostics(value: unknown): DiagnoseResult | null {
  if (!isRecord(value) || !isRecord(value.stats) ||
    (value.status !== "ok" && value.status !== "degraded")) return null;

  const summary = value.stats.__summary__;
  if (
    !isRecord(summary) ||
    !isNonNegativeInteger(summary.total_failures) ||
    !isNonNegativeInteger(summary.failing_endpoints) ||
    !isNonNegativeInteger(summary.empty_endpoints)
  ) {
    return null;
  }

  const checks: Record<string, DiagnoseCheck> = {};
  for (const [name, rawCheck] of Object.entries(value.stats)) {
    if (name === "__summary__") continue;
    if (!isRecord(rawCheck) || !isNonNegativeInteger(rawCheck.failures) ||
      (rawCheck.current_status !== "healthy" && rawCheck.current_status !== "failed" && rawCheck.current_status !== "empty")) {
      return null;
    }

    if (rawCheck.current_status !== "healthy") {
      checks[name] = {
        status: rawCheck.current_status === "empty" ? "warn" : "fail",
        ...(typeof rawCheck.last_error === "string"
          ? { error: rawCheck.last_error }
          : {}),
        ...(typeof rawCheck.last_error_code === "string"
          ? { errorCode: rawCheck.last_error_code }
          : {}),
      };
    } else {
      checks[name] = { status: "pass" };
    }
  }

  const degraded =
    value.status !== "ok" ||
    summary.failing_endpoints > 0 ||
    summary.empty_endpoints > 0 ||
    Object.values(checks).some((check) => check.status !== "pass");
  const { issues, backupFailures } = partitionDiagnostics(checks);
  const onlyRedundantIndexFailures = backupFailures.length > 0 && issues.length === 0;
  return {
    status: onlyRedundantIndexFailures ? "healthy_with_warnings" : degraded ? "degraded" : "healthy",
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

  if (diagnoseStatus === "healthy" || diagnoseStatus === "healthy_with_warnings") {
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
