import type {
  ChainNode,
  ChainStage,
  HotNewsItem,
  MacroBrief,
  MarketDataStatus,
  MarketEnvelope,
  MarketIndex,
  MarketLimitation,
  MarketMeta,
  MarketSourceDiagnostic,
  MarketSourceStatus,
  SectorItem,
  SectorDetail,
  SectorStock,
} from "@/lib/types/market";

const MARKET_STATUSES = new Set<MarketDataStatus>([
  "success",
  "partial",
  "empty",
  "stale",
]);
const SOURCE_STATUSES = new Set<MarketSourceStatus>([
  "success_data", "success_empty", "failed", "unsupported", "stale", "conflicted",
]);

export class MarketContractError extends Error {
  constructor() {
    super("市场接口响应契约不兼容，请更新前后端服务");
    this.name = "MarketContractError";
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function isNonNegativeInteger(value: unknown): value is number {
  return Number.isInteger(value) && isFiniteNumber(value) && value >= 0;
}

function isNonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === "string");
}

function isLimitation(value: unknown): value is MarketLimitation {
  return (
    isRecord(value) &&
    isNonEmptyString(value.code) &&
    isNonEmptyString(value.message) &&
    (value.index_code === null || typeof value.index_code === "string")
  );
}

function isTimestamp(value: unknown): value is string {
  return (
    typeof value === "string" &&
    /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) &&
    Number.isFinite(Date.parse(value))
  );
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === "string";
}

function isSourceDiagnostic(value: unknown): value is MarketSourceDiagnostic {
  return (
    isRecord(value) &&
    isNonEmptyString(value.index_code) &&
    isNonEmptyString(value.source_id) &&
    isNonEmptyString(value.upstream_id) &&
    SOURCE_STATUSES.has(value.status as MarketSourceStatus) &&
    isNonNegativeInteger(value.latency_ms) &&
    (value.as_of === null || isTimestamp(value.as_of)) &&
    isNullableString(value.error_code) &&
    isNullableString(value.error_message)
  );
}

function parseMeta(value: unknown): MarketMeta {
  if (
    !isRecord(value) ||
    !MARKET_STATUSES.has(value.status as MarketDataStatus) ||
    typeof value.cached !== "boolean" ||
    !isNonNegativeInteger(value.latency_ms) ||
    !isStringArray(value.missing_codes) ||
    !isStringArray(value.failed_sources) ||
    !Array.isArray(value.limitations) ||
    !value.limitations.every(isLimitation) ||
    !Array.isArray(value.source_diagnostics) ||
    !value.source_diagnostics.every(isSourceDiagnostic) ||
    !isNullableString(value.sort_requested) ||
    !isNullableString(value.sort_applied)
  ) {
    throw new MarketContractError();
  }
  if (value.status === "stale" && !value.cached) {
    throw new MarketContractError();
  }
  if (
    value.status === "partial" &&
    value.missing_codes.length === 0 &&
    value.failed_sources.length === 0 &&
    value.limitations.length === 0
  ) {
    throw new MarketContractError();
  }
  return value as unknown as MarketMeta;
}

function parseEnvelope<T>(
  value: unknown,
  parseData: (data: unknown) => T,
  isEmpty: (data: T) => boolean,
): MarketEnvelope<T> {
  if (!isRecord(value) || !("data" in value) || !("meta" in value)) {
    throw new MarketContractError();
  }
  const data = parseData(value.data);
  const meta = parseMeta(value.meta);
  if ((meta.status === "empty") !== isEmpty(data)) {
    throw new MarketContractError();
  }
  return { data, meta };
}

function isMarketIndex(value: unknown): value is MarketIndex {
  return (
    isRecord(value) &&
    isNonEmptyString(value.code) &&
    isNonEmptyString(value.name) &&
    isFiniteNumber(value.price) &&
    value.price > 0 &&
    isFiniteNumber(value.change) &&
    isFiniteNumber(value.change_pct) &&
    isTimestamp(value.as_of) &&
    isNonNegativeInteger(value.source_count) &&
    value.source_count >= 1 &&
    (value.display_source === null || isNonEmptyString(value.display_source)) &&
    (value.source_count === 1 ? isNonEmptyString(value.display_source) : value.display_source === null) &&
    typeof value.cached === "boolean"
  );
}

function isSector(value: unknown): value is SectorItem {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.name) &&
    isFiniteNumber(value.change_pct) &&
    (value.fund_flow === null || isFiniteNumber(value.fund_flow)) &&
    (value.heat === "high" || value.heat === "medium" || value.heat === "low") &&
    isStringArray(value.top_stocks) &&
    isNonNegativeInteger(value.rank)
  );
}

function isMacroBrief(value: unknown): value is MacroBrief {
  return (
    isRecord(value) &&
    isNonEmptyString(value.summary) &&
    typeof value.generated_at === "string" &&
    typeof value.market_style === "string" &&
    isStringArray(value.risk_tips) &&
    isStringArray(value.hot_topics)
  );
}

function isHotNews(value: unknown): value is HotNewsItem {
  return (
    isRecord(value) &&
    isNonEmptyString(value.title) &&
    (value.date === null || isNonEmptyString(value.date)) &&
    isNonEmptyString(value.source) &&
    typeof value.url === "string"
  );
}

function parseArray<T>(value: unknown, predicate: (item: unknown) => item is T): T[] {
  if (!Array.isArray(value) || !value.every(predicate)) {
    throw new MarketContractError();
  }
  return value;
}

export function parseIndicesEnvelope(value: unknown): MarketEnvelope<MarketIndex[]> {
  const envelope = parseEnvelope(
    value,
    (data) => parseArray(data, isMarketIndex),
    (data) => data.length === 0,
  );
  if (
    (envelope.meta.status === "success" && envelope.data.some((item) => item.source_count < 2 || item.cached)) ||
    (envelope.meta.status === "stale" && envelope.data.some((item) => !item.cached))
  ) {
    throw new MarketContractError();
  }
  return envelope;
}

export function parseSectorsEnvelope(value: unknown): MarketEnvelope<SectorItem[]> {
  const envelope = parseEnvelope(
    value,
    (data) => parseArray(data, isSector),
    (data) => data.length === 0,
  );
  const hasUnknownFundFlow = envelope.data.some((item) => item.fund_flow === null);
  const hasFundFlowLimitation = envelope.meta.limitations.some(
    (item) => item.code === "FUND_FLOW_UNAVAILABLE",
  );
  if (
    (hasUnknownFundFlow && (!hasFundFlowLimitation || envelope.meta.sort_applied === "fund_flow")) ||
    (envelope.meta.sort_applied === "fund_flow" && hasUnknownFundFlow)
  ) {
    throw new MarketContractError();
  }
  return envelope;
}

function isSectorStock(value: unknown): value is SectorStock {
  return (
    isRecord(value) &&
    isNonEmptyString(value.code) &&
    isNonEmptyString(value.name) &&
    isFiniteNumber(value.price) &&
    isFiniteNumber(value.change_pct) &&
    (value.fund_flow === null || isFiniteNumber(value.fund_flow)) &&
    isNonEmptyString(value.ai_rating)
  );
}

function isChainNode(value: unknown): value is ChainNode {
  return (
    isRecord(value) &&
    isNonEmptyString(value.name) &&
    isStringArray(value.companies) &&
    typeof value.is_bottleneck === "boolean"
  );
}

function isChainStage(value: unknown): value is ChainStage {
  return (
    isRecord(value) &&
    isNonEmptyString(value.stage) &&
    typeof value.description === "string" &&
    Array.isArray(value.nodes) &&
    value.nodes.every(isChainNode)
  );
}

function isSectorDetail(value: unknown): value is SectorDetail {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.name) &&
    isFiniteNumber(value.change_pct) &&
    (value.fund_flow === null || isFiniteNumber(value.fund_flow)) &&
    (value.heat === "high" || value.heat === "medium" || value.heat === "low") &&
    Array.isArray(value.chain_map) &&
    value.chain_map.every(isChainStage) &&
    typeof value.ai_analysis === "string" &&
    Array.isArray(value.stocks) &&
    value.stocks.every(isSectorStock)
  );
}

export function parseSectorDetailEnvelope(value: unknown): MarketEnvelope<SectorDetail> {
  const envelope = parseEnvelope(
    value,
    (data) => {
      if (!isSectorDetail(data)) throw new MarketContractError();
      return data;
    },
    () => false,
  );
  const hasUnknownFundFlow = envelope.data.fund_flow === null ||
    envelope.data.stocks.some((item) => item.fund_flow === null);
  if (
    hasUnknownFundFlow &&
    !envelope.meta.limitations.some((item) => item.code === "FUND_FLOW_UNAVAILABLE")
  ) {
    throw new MarketContractError();
  }
  return envelope;
}

export function parseMacroBriefEnvelope(
  value: unknown,
): MarketEnvelope<MacroBrief | null> {
  return parseEnvelope(
    value,
    (data) => {
      if (data === null) return null;
      if (!isMacroBrief(data)) throw new MarketContractError();
      return data;
    },
    (data) => data === null,
  );
}

export function parseHotNewsEnvelope(value: unknown): MarketEnvelope<HotNewsItem[]> {
  return parseEnvelope(
    value,
    (data) => parseArray(data, isHotNews),
    (data) => data.length === 0,
  );
}
