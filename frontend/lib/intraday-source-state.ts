import type { IntradayBattlefield } from "@/lib/types/stock";

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
  const match = asOf?.match(/T(\d{2}:\d{2})/);
  return match ? `数据时间 ${match[1]}` : "数据时间暂不可用";
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
      return {
        label: "多源交叉验证通过",
        detail: time,
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
