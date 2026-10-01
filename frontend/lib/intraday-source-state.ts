import type {
  EvidenceSourceStatus,
  IntradayBattlefield,
  IntradayPricePoint,
} from "@/lib/types/stock";

export type IntradaySourceTone =
  | "verified"
  | "warning"
  | "conflict"
  | "unavailable";

export interface IntradaySourceState {
  label: string;
  detail: string;
  tone: IntradaySourceTone;
}

export type IntradayPanelMode =
  | "loading"
  | "network_error"
  | "stale_error"
  | "unavailable"
  | "usable";

export interface IntradayLineDatum {
  time: number;
  value: number;
}

export interface IntradayDiagnosticDisclosure {
  sourceId: string;
  sourceName: string;
  statusLabel: string;
  fetchedTime: string;
  checkpointCount: number;
  errorMessage: string | null;
}

export interface IntradayRequestErrorCopy {
  title: string;
  detail: string;
}

const SOURCE_STATUS_LABELS: Record<EvidenceSourceStatus, string> = {
  success_data: "数据可用",
  success_empty: "返回为空",
  failed: "请求失败",
  unsupported: "暂不支持",
  stale: "数据已过期",
  conflicted: "数据存在分歧",
};

const shanghaiClock = new Intl.DateTimeFormat("zh-CN", {
  timeZone: "Asia/Shanghai",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

function canonicalSourceName(data: IntradayBattlefield): string | null {
  const canonicalSourceId = data.canonical_source_id;
  if (canonicalSourceId === null) return null;

  const diagnostic = data.source_diagnostics.find(
    (candidate) => candidate.source_id === canonicalSourceId,
  );
  const sourceName = diagnostic?.source_name.trim();
  return sourceName || null;
}

function dataTime(asOf: string | null): string {
  return asOf ? `数据时间 ${clockTime(asOf)}` : "数据时间暂不可用";
}

function availableSourceNames(data: IntradayBattlefield): string[] {
  const available = new Set(data.available_source_ids);
  return data.source_diagnostics.flatMap((diagnostic) => {
    const name = diagnostic.source_name.trim();
    return available.has(diagnostic.source_id) && name ? [name] : [];
  });
}

function clockTime(timestamp: string): string {
  if (!/(?:Z|[+-]\d{2}:\d{2})$/i.test(timestamp)) {
    return "时间格式无时区";
  }
  const milliseconds = Date.parse(timestamp);
  return Number.isFinite(milliseconds)
    ? shanghaiClock.format(new Date(milliseconds))
    : "时间格式无效";
}

export function resolveIntradayPanelMode({
  data,
  isLoading,
  isError,
}: {
  data: IntradayBattlefield | undefined;
  isLoading: boolean;
  isError: boolean;
}): IntradayPanelMode {
  if (isLoading && data === undefined) return "loading";
  if (isError && data === undefined) return "network_error";
  if (isError && data?.usable && data.price_points.length > 0) {
    return "stale_error";
  }
  if (data?.usable && data.price_points.length > 0) return "usable";
  return "unavailable";
}

/** Converts only timestamp and close into line-series data; OHLC is never inferred. */
export function toIntradayLineData(
  points: readonly Pick<IntradayPricePoint, "timestamp" | "close">[],
): IntradayLineDatum[] {
  const bySecond = new Map<number, IntradayLineDatum>();
  for (const point of points) {
    const milliseconds = Date.parse(point.timestamp);
    if (!Number.isFinite(milliseconds) || !Number.isFinite(point.close)) {
      continue;
    }
    const time = Math.floor(milliseconds / 1_000);
    bySecond.set(time, { time, value: point.close });
  }
  return [...bySecond.values()].sort((left, right) => left.time - right.time);
}

export function formatShanghaiChartTime(unixSeconds: number): string {
  return shanghaiClock.format(new Date(unixSeconds * 1_000));
}

/** Keeps source disclosure anchored to diagnostics returned by the API. */
export function describeIntradayDiagnostics(
  data: IntradayBattlefield,
): IntradayDiagnosticDisclosure[] {
  return data.source_diagnostics.map((diagnostic) => ({
    sourceId: diagnostic.source_id,
    sourceName: diagnostic.source_name.trim() || "未命名来源",
    statusLabel: SOURCE_STATUS_LABELS[diagnostic.status],
    fetchedTime: clockTime(diagnostic.fetched_at),
    checkpointCount: diagnostic.checkpoint_count,
    errorMessage: diagnostic.error_message,
  }));
}

/** Maps transport/HTTP/contract failures without calling every failure a network fault. */
export function describeIntradayRequestError(
  error: unknown,
): IntradayRequestErrorCopy {
  const candidate =
    typeof error === "object" && error !== null
      ? (error as { name?: unknown; code?: unknown; status?: unknown })
      : {};
  if (candidate.name === "IntradayContractError") {
    return {
      title: "分时接口版本不兼容",
      detail: "前后端数据格式尚未对齐，已停止解析，避免把错误字段画成行情。",
    };
  }
  if (candidate.code === "RATE_LIMITED" || candidate.status === 429) {
    return {
      title: "分时请求过于频繁",
      detail: "数据服务要求稍后再试，当前没有新的来源诊断。",
    };
  }
  if (candidate.code === "NETWORK_ERROR" || candidate.status === 0) {
    return {
      title: "分时接口连接失败",
      detail: "当前没有收到来源诊断，不能判断是哪一家数据源异常。",
    };
  }
  if (typeof candidate.status === "number" && candidate.status >= 500) {
    return {
      title: "分时服务暂不可用",
      detail: "服务端未能完成请求，当前没有新的来源诊断。",
    };
  }
  return {
    title: "分时数据请求失败",
    detail: "请求未完成，当前没有新的来源诊断。",
  };
}

/**
 * Maps backend verification facts to the one persistent source-disclosure copy.
 * It intentionally never changes a usable response into a blocked UI flow.
 */
export function describeIntradaySourceState(
  data: IntradayBattlefield,
): IntradaySourceState {
  const time = dataTime(data.as_of);

  switch (data.verification_status) {
    case "multi_source_verified":
      const sourceNames = availableSourceNames(data);
      return {
        label: "多源交叉验证通过",
        detail: `${sourceNames.length > 0 ? `${sourceNames.join(" + ")} · ` : ""}${time}`,
        tone: "verified",
      };
    case "single_source":
      return {
        label: `单一数据源 · ${canonicalSourceName(data) ?? "来源待确认"}`,
        detail: `未交叉验证 · ${time}`,
        tone: "warning",
      };
    case "source_conflict":
      return {
        label: `数据源存在分歧 · 当前采用${canonicalSourceName(data) ?? "来源待确认"}`,
        detail: `数据源之间存在分歧 · ${time}`,
        tone: "conflict",
      };
    case "unavailable":
      return {
        label: "分时数据暂不可用",
        detail: "暂无通过本地校验的数据源",
        tone: "unavailable",
      };
  }
}
