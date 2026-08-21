import type {
  EvidenceAssessment,
  EvidenceSourceStatus,
  IntradayBar,
  IntradayBattlefield,
  IntradayBattlefieldSnapshot,
  IntradayPricePoint,
  IntradaySourceDiagnostic,
  IntradayVerificationStatus,
} from "@/lib/types/stock";

const VERIFICATION_STATUSES = new Set<IntradayVerificationStatus>([
  "multi_source_verified",
  "single_source",
  "source_conflict",
  "unavailable",
]);
const SOURCE_STATUSES = new Set<EvidenceSourceStatus>([
  "success_data",
  "success_empty",
  "failed",
  "unsupported",
  "stale",
  "conflicted",
]);

export class IntradayContractError extends Error {
  constructor() {
    super("分时接口响应契约不兼容，请更新后端服务");
    this.name = "IntradayContractError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isFiniteAtLeast(value: unknown, minimum: number): value is number {
  return typeof value === "number" && Number.isFinite(value) && value >= minimum;
}

function isNullableFinite(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isFinite(value));
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isPricePoint(value: unknown, symbol: string): value is IntradayPricePoint {
  return (
    isRecord(value) &&
    value.code === symbol &&
    isTimestamp(value.timestamp) &&
    isFiniteAtLeast(value.close, 0.000001) &&
    Number.isInteger(value.cumulative_volume) &&
    isFiniteAtLeast(value.cumulative_volume, 0) &&
    isFiniteAtLeast(value.cumulative_amount, 0) &&
    (value.state === "final" || value.state === "provisional")
  );
}

function isBar(value: unknown, symbol: string): value is IntradayBar {
  return (
    isRecord(value) &&
    value.code === symbol &&
    isTimestamp(value.timestamp) &&
    isFiniteAtLeast(value.open, 0.000001) &&
    isFiniteAtLeast(value.high, 0.000001) &&
    isFiniteAtLeast(value.low, 0.000001) &&
    isFiniteAtLeast(value.close, 0.000001) &&
    value.high >= value.open &&
    value.high >= value.close &&
    value.high >= value.low &&
    value.low <= value.open &&
    value.low <= value.close &&
    Number.isInteger(value.volume) &&
    isFiniteAtLeast(value.volume, 0) &&
    isFiniteAtLeast(value.amount, 0) &&
    (value.state === "final" || value.state === "provisional")
  );
}

function hasStrictlyOrderedTimestamps(
  values: readonly { timestamp: string }[],
): boolean {
  let previous = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    const time = Date.parse(value.timestamp);
    if (!Number.isFinite(time) || time <= previous) return false;
    previous = time;
  }
  return true;
}

function isSourceDiagnostic(value: unknown): value is IntradaySourceDiagnostic {
  return (
    isRecord(value) &&
    typeof value.source_id === "string" &&
    typeof value.source_name === "string" &&
    typeof value.upstream_id === "string" &&
    SOURCE_STATUSES.has(value.status as EvidenceSourceStatus) &&
    isTimestamp(value.fetched_at) &&
    isNullableString(value.error_code) &&
    isNullableString(value.error_message) &&
    Number.isInteger(value.checkpoint_count) &&
    isFiniteAtLeast(value.checkpoint_count, 0) &&
    (value.latest_timestamp === null || isTimestamp(value.latest_timestamp))
  );
}

function isAssessment(value: unknown): value is EvidenceAssessment {
  return (
    isRecord(value) &&
    value.capability === "intraday" &&
    typeof value.complete === "boolean" &&
    isStringArray(value.successful_upstream_ids) &&
    isStringArray(value.successful_source_ids) &&
    isStringArray(value.failed_source_ids) &&
    isStringArray(value.discovery_only_source_ids) &&
    isStringArray(value.unusable_source_ids) &&
    isStringArray(value.missing_required_upstream_ids) &&
    Number.isInteger(value.missing_independent_upstreams) &&
    isFiniteAtLeast(value.missing_independent_upstreams, 0)
  );
}

function isSnapshot(
  value: unknown,
  symbol: string,
): value is IntradayBattlefieldSnapshot {
  return (
    isRecord(value) &&
    value.code === symbol &&
    value.evidence_level === "L1" &&
    isTimestamp(value.as_of) &&
    isFiniteAtLeast(value.current_price, 0.000001) &&
    (value.current_bar_state === "final" ||
      value.current_bar_state === "provisional") &&
    (value.session_vwap === null ||
      isFiniteAtLeast(value.session_vwap, 0.000001)) &&
    isNullableFinite(value.vwap_deviation_pct) &&
    (value.vwap_position === "above" ||
      value.vwap_position === "at" ||
      value.vwap_position === "below" ||
      value.vwap_position === "unavailable") &&
    (value.opening_range_high === null ||
      isFiniteAtLeast(value.opening_range_high, 0.000001)) &&
    (value.opening_range_low === null ||
      isFiniteAtLeast(value.opening_range_low, 0.000001)) &&
    (value.opening_range_high === null ||
      value.opening_range_low === null ||
      value.opening_range_high >= value.opening_range_low) &&
    Number.isInteger(value.cumulative_volume) &&
    isFiniteAtLeast(value.cumulative_volume, 0) &&
    (value.relative_volume === null ||
      isFiniteAtLeast(value.relative_volume, 0)) &&
    (value.relative_volume_sample_days === null ||
      (Number.isInteger(value.relative_volume_sample_days) &&
        isFiniteAtLeast(value.relative_volume_sample_days, 1))) &&
    value.attribution_supported === false &&
    isStringArray(value.limitations)
  );
}

function hasSourceInvariants(value: {
  usable: boolean;
  verification_status: IntradayVerificationStatus;
  canonical_source_id: string | null;
  available_source_ids: string[];
  source_diagnostics: IntradaySourceDiagnostic[];
  price_points: IntradayPricePoint[];
}): boolean {
  const diagnosticIds = new Set(
    value.source_diagnostics.map((diagnostic) => diagnostic.source_id),
  );
  const available = new Set(value.available_source_ids);
  if (
    available.size !== value.available_source_ids.length ||
    value.available_source_ids.some((sourceId) => !diagnosticIds.has(sourceId))
  ) {
    return false;
  }
  if (value.usable) {
    if (
      value.price_points.length === 0 ||
      value.canonical_source_id === null ||
      !available.has(value.canonical_source_id)
    ) {
      return false;
    }
  } else if (value.price_points.length > 0) {
    return false;
  }
  if (value.verification_status === "single_source") return available.size === 1;
  if (value.verification_status === "multi_source_verified") {
    return available.size >= 2;
  }
  if (value.verification_status === "source_conflict") {
    return available.size >= 2;
  }
  return (
    !value.usable &&
    available.size === 0 &&
    value.canonical_source_id === null
  );
}

/** Rejects stale/legacy JSON at the HTTP boundary before React renders it. */
export function parseIntradayBattlefield(value: unknown): IntradayBattlefield {
  if (!isRecord(value)) {
    throw new IntradayContractError();
  }
  const symbol = value.symbol;
  if (typeof symbol !== "string" || !/^\d{6}$/.test(symbol)) {
    throw new IntradayContractError();
  }
  if (
    typeof value.complete !== "boolean" ||
    typeof value.usable !== "boolean" ||
    !VERIFICATION_STATUSES.has(
      value.verification_status as IntradayVerificationStatus,
    ) ||
    !isNullableString(value.canonical_source_id) ||
    !isStringArray(value.available_source_ids) ||
    !isStringArray(value.failed_source_ids) ||
    !(value.as_of === null || isTimestamp(value.as_of)) ||
    !isTimestamp(value.collected_at) ||
    !isAssessment(value.assessment) ||
    !Array.isArray(value.source_diagnostics) ||
    !value.source_diagnostics.every(isSourceDiagnostic) ||
    !Array.isArray(value.bars) ||
    !value.bars.every((bar) => isBar(bar, symbol)) ||
    !hasStrictlyOrderedTimestamps(value.bars) ||
    !Array.isArray(value.price_points) ||
    !value.price_points.every((point) => isPricePoint(point, symbol)) ||
    !hasStrictlyOrderedTimestamps(value.price_points) ||
    !(value.snapshot === null || isSnapshot(value.snapshot, symbol))
  ) {
    throw new IntradayContractError();
  }

  const parsed = value as unknown as IntradayBattlefield;
  if (
    !hasSourceInvariants(parsed) ||
    (parsed.snapshot !== null &&
      parsed.as_of !== null &&
      Date.parse(parsed.snapshot.as_of) !== Date.parse(parsed.as_of))
  ) {
    throw new IntradayContractError();
  }
  return parsed;
}
