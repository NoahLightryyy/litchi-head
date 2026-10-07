"use client";

import { useMemo, useRef, useState } from "react";
import { stepPriceWindow, type PriceWindow, type SemanticZoom, type ZoomControls, type ZoomDirection } from "@/lib/chart-zoom";
import { FiveDayChart } from "./five-day-chart";
import { KlineChart } from "./kline-chart";
import {
  Activity,
  AlertTriangle,
  ChevronDown,
  Database,
  RefreshCw,
  WifiOff,
} from "lucide-react";

import { IntradayLineChart } from "@/components/stock/intraday-line-chart";
import {
  describeIntradayDiagnostics,
  describeIntradayRequestError,
  describeIntradaySourceState,
  resolveIntradayPanelMode,
  type IntradaySourceState,
} from "@/lib/intraday-source-state";
import { intradayReferenceClose } from "@/lib/intraday-percent";
import { useStockQuote, useIntradayBattlefield } from "@/lib/hooks/use-stock";
import type {
  IntradayBattlefield,
  IntradayBattlefieldSnapshot,
} from "@/lib/types/stock";

interface IntradayBattlefieldPanelProps {
  code: string;
}

const TONE_STYLES: Record<IntradaySourceState["tone"], string> = {
  verified: "border-accent-green/35 bg-accent-green/10 text-accent-green",
  warning: "border-accent-gold/35 bg-accent-gold/10 text-accent-gold",
  conflict: "border-accent-red/35 bg-accent-red/10 text-accent-red",
  unavailable: "border-bg-elevated bg-bg-tertiary text-text-secondary",
};

const compactNumber = new Intl.NumberFormat("zh-CN", {
  notation: "compact",
  maximumFractionDigits: 2,
});

function SourceStatusBadge({ state }: { state: IntradaySourceState }) {
  return (
    <div
      className={`min-w-56 rounded-md border px-3 py-2 text-right ${TONE_STYLES[state.tone]}`}
      aria-live="polite"
    >
      <div className="text-xs font-semibold">{state.label}</div>
      <div className="mt-0.5 text-[11px] opacity-75">{state.detail}</div>
    </div>
  );
}

function MetricRow({
  label,
  explanation,
  value,
}: {
  label: string;
  explanation: string;
  value: string;
}) {
  return (
    <div className="flex items-end justify-between gap-4 border-b border-bg-tertiary py-3 last:border-0">
      <div>
        <div className="text-xs font-medium text-text-secondary">{label}</div>
        <div className="mt-0.5 text-[10px] leading-4 text-text-muted">
          {explanation}
        </div>
      </div>
      <div className="kpi shrink-0 text-base font-semibold text-text-primary">
        {value}
      </div>
    </div>
  );
}

function SnapshotMetrics({
  snapshot,
  data,
}: {
  snapshot: IntradayBattlefieldSnapshot | null;
  data: IntradayBattlefield;
}) {
  const latestPoint = data.price_points.at(-1);
  const currentPrice = snapshot?.current_price ?? latestPoint?.close;
  const volume = snapshot?.cumulative_volume ?? latestPoint?.cumulative_volume;

  return (
    <aside className="rounded-md border border-bg-tertiary bg-bg-primary px-4">
      {currentPrice !== undefined && (
        <MetricRow
          label="当前价格"
          explanation="最近一个已结束或进行中的分钟点"
          value={currentPrice.toFixed(2)}
        />
      )}
      {snapshot?.session_vwap !== null && snapshot?.session_vwap !== undefined && (
        <MetricRow
          label="VWAP"
          explanation="成交量加权平均价，用成交量衡量盘中平均成本"
          value={snapshot.session_vwap.toFixed(2)}
        />
      )}
      {volume !== undefined && (
        <MetricRow
          label="累计成交量"
          explanation="截至当前分钟的累计成交股数"
          value={`${compactNumber.format(volume)} 股`}
        />
      )}
      {snapshot?.relative_volume !== null &&
        snapshot?.relative_volume !== undefined && (
          <MetricRow
            label="同期量比"
            explanation={`对比同一分钟的历史中位数${snapshot.relative_volume_sample_days ? ` · ${snapshot.relative_volume_sample_days} 日样本` : ""}`}
            value={`${snapshot.relative_volume.toFixed(2)}×`}
          />
        )}
    </aside>
  );
}

function SourceDisclosure({ data }: { data: IntradayBattlefield }) {
  const diagnostics = describeIntradayDiagnostics(data);

  return (
    <details className="group mt-4 border-t border-bg-tertiary pt-3">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-medium text-text-secondary transition-colors hover:text-text-primary">
        <Database className="h-3.5 w-3.5" />
        查看数据来源
        <span className="text-text-muted">{diagnostics.length} 路诊断</span>
        <ChevronDown className="ml-auto h-3.5 w-3.5 transition-transform group-open:rotate-180" />
      </summary>
      <div className="mt-3 grid gap-2 md:grid-cols-2">
        {diagnostics.map((diagnostic, index) => (
          <div
            key={diagnostic.sourceId || `${diagnostic.sourceName}-${index}`}
            className="rounded-md border border-bg-tertiary bg-bg-primary p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs font-semibold text-text-primary">
                {diagnostic.sourceName}
              </span>
              <span className="text-[11px] text-text-secondary">
                {diagnostic.statusLabel}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-text-muted">
              <span>抓取 {diagnostic.fetchedTime}</span>
              <span>检查点 {diagnostic.checkpointCount}</span>
            </div>
            {diagnostic.errorMessage && (
              <p className="mt-2 break-words text-xs leading-5 text-accent-red">
                {diagnostic.errorMessage}
              </p>
            )}
          </div>
        ))}
      </div>
    </details>
  );
}

function LoadingState() {
  return (
    <div
      className="grid animate-pulse gap-4 lg:grid-cols-[minmax(0,1fr)_15rem]"
      role="status"
      aria-label="正在获取并核验分时数据"
    >
      <div className="h-72 rounded-md bg-bg-primary" />
      <div className="h-72 rounded-md bg-bg-primary" />
    </div>
  );
}

/** 盘中价格事实、指标解释与逐源诊断的正式展示面板。 */
export function IntradayBattlefieldPanel({ code }: IntradayBattlefieldPanelProps) {
  const [priceWindow, setPriceWindow] = useState<PriceWindow>("intraday");
  const controls = useRef<ZoomControls | null>(null);
  const entry = useRef<ZoomDirection | null>(null);
  const [zoomReady, setZoomReady] = useState(false);
  const zoom = useMemo<SemanticZoom>(() => ({controls, entry, window: priceWindow, onReady: setZoomReady,
    onOut: priceWindow === "daily" ? undefined : () => setPriceWindow(v => stepPriceWindow(v, "out")),
    onIn: priceWindow === "intraday" ? undefined : () => setPriceWindow(v => stepPriceWindow(v, "in")),
    inThreshold: priceWindow === "five-day" ? 260 : 8,
  }), [priceWindow]);
  const query = useIntradayBattlefield(code);
  const quote = useStockQuote(code);
  const referenceClose = intradayReferenceClose(code, quote.data, query.data?.price_points ?? []);
  const mode = resolveIntradayPanelMode({
    data: query.data,
    isLoading: query.isLoading,
    isError: query.isError,
  });
  const requestError = describeIntradayRequestError(query.error);
  const sourceState: IntradaySourceState = query.data
    ? describeIntradaySourceState(query.data)
    : mode === "network_error"
      ? {
          label: requestError.title,
          detail: "未取得新的数据来源诊断",
          tone: "unavailable",
        }
      : {
          label: "正在核验数据来源",
          detail: "等待分钟数据返回",
          tone: "unavailable",
        };

  return (
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
      <header className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-start">
        <div>
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-accent-gold" />
            <h2 className="text-sm font-semibold text-text-primary">价格走势</h2>
            {query.isFetching && !query.isLoading && (
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-accent-blue" />
            )}
          </div>
          <p className="mt-1 text-xs text-text-muted">
            用 ＋ / － 连续缩放视野，衔接当日 ↔ 五日 ↔ 日 K；滚轮用于滚动页面
          </p>
        </div>
        {priceWindow === "intraday" && <SourceStatusBadge state={sourceState} />}
      </header>

      <nav aria-label="走势时间范围" className="mb-4 flex flex-wrap items-center gap-2">
        {([["intraday", "当日分时"], ["five-day", "五日分时"], ["daily", "日 K"]] as const).map(([value, label]) =>
          <button key={value} aria-pressed={priceWindow === value} onClick={() => { entry.current = null; setPriceWindow(value); }} className={`rounded px-3 py-2 text-sm ${priceWindow === value ? "bg-accent-blue text-white" : "bg-bg-tertiary text-text-secondary"}`}>{label}</button>)}
        <button aria-label="放大图表" disabled={!zoomReady} className="ml-auto rounded border border-bg-tertiary px-3 py-2 text-xs disabled:opacity-40" onClick={() => controls.current?.step("in")}>＋ 放大</button>
        <button aria-label="缩小图表" disabled={!zoomReady} className="rounded border border-bg-tertiary px-3 py-2 text-xs disabled:opacity-40" onClick={() => controls.current?.step("out")}>－ 缩小</button>
      </nav>
      {priceWindow === "five-day" && <FiveDayChart code={code} zoom={zoom} />}
      {priceWindow === "daily" && <KlineChart code={code} zoom={zoom} />}
      {priceWindow === "intraday" && mode === "loading" && <LoadingState />}

      {priceWindow === "intraday" && mode === "network_error" && (
        <div className="flex min-h-56 flex-col items-center justify-center rounded-md border border-bg-tertiary bg-bg-primary px-6 text-center">
          <WifiOff className="mb-3 h-7 w-7 text-accent-red" />
          <p className="text-sm font-medium text-text-primary">
            {requestError.title}
          </p>
          <p className="mt-1 text-xs text-text-muted">
            {requestError.detail}
          </p>
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="mt-4 flex items-center gap-2 rounded-md border border-bg-elevated bg-bg-tertiary px-3 py-2 text-xs text-text-secondary transition-colors hover:text-text-primary"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            重新获取
          </button>
        </div>
      )}

      {priceWindow === "intraday" && mode === "unavailable" && query.data && (
        <>
          <div className="flex min-h-44 items-start gap-3 rounded-md border border-bg-tertiary bg-bg-primary p-5">
            <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-accent-gold" />
            <div>
              <p className="text-sm font-medium text-text-primary">
                实时数据暂不可用
              </p>
              <p className="mt-1 text-xs leading-5 text-text-muted">
                当前没有通过本地结构与时间校验的分钟序列，因此不绘图。逐源返回状态见下方，页面不会用示意数据替代真实行情。
              </p>
            </div>
          </div>
          <SourceDisclosure data={query.data} />
        </>
      )}

      {priceWindow === "intraday" && (mode === "usable" || mode === "stale_error") && query.data && (
        <>
          {mode === "stale_error" && (
            <div
              className="mb-4 flex flex-col justify-between gap-3 rounded-md border border-accent-red/40 bg-accent-red/10 p-3 text-xs text-accent-red sm:flex-row sm:items-center"
              role="alert"
            >
              <span>
                刷新失败，当前保留最后一次成功数据 · {sourceState.detail}
              </span>
              <button
                type="button"
                onClick={() => void query.refetch()}
                className="flex w-fit items-center gap-2 rounded-md border border-accent-red/40 px-3 py-1.5 font-medium"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                立即重试
              </button>
            </div>
          )}
          <div className="grid min-w-0 grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_15rem]">
            <div className="min-w-0">
              <IntradayLineChart points={query.data.price_points} zoom={zoom} referenceClose={referenceClose} />
              <div className="mt-2 flex items-center justify-between text-xs text-text-muted">
                <span>折线仅表示分钟价格，不代表 K 线开高低收</span>
                <span>{query.data.price_points.length} 个价格点</span>
              </div>
            </div>
            <SnapshotMetrics snapshot={query.data.snapshot} data={query.data} />
          </div>
          <SourceDisclosure data={query.data} />
        </>
      )}
    </section>
  );
}
