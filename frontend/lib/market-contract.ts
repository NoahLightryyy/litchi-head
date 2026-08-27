import type {
  HotNewsItem,
  MacroBrief,
  MarketDataStatus,
  MarketEnvelope,
  MarketIndex,
  MarketLimitation,
  MarketMeta,
  SectorItem,
} from "@/lib/types/market";

const MARKET_STATUSES = new Set<MarketDataStatus>([
  "success",
  "partial",
  "empty",
  "stale",
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
    isNonEmptyString(value.message)
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
    !value.limitations.every(isLimitation)
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
    isFiniteNumber(value.change_pct)
  );
}

function isSector(value: unknown): value is SectorItem {
  return (
    isRecord(value) &&
    isNonEmptyString(value.id) &&
    isNonEmptyString(value.name) &&
    isFiniteNumber(value.change_pct) &&
    isFiniteNumber(value.fund_flow) &&
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
  return parseEnvelope(
    value,
    (data) => parseArray(data, isMarketIndex),
    (data) => data.length === 0,
  );
}

export function parseSectorsEnvelope(value: unknown): MarketEnvelope<SectorItem[]> {
  return parseEnvelope(
    value,
    (data) => parseArray(data, isSector),
    (data) => data.length === 0,
  );
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
