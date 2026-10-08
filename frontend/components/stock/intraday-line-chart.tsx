"use client";

import { useEffect, useId, useMemo, useRef } from "react";
import { minuteActivityRows, minuteQuoteRows, type MinuteReference } from "@/lib/minute-quote";
import { bindChartZoom, type SemanticZoom } from "@/lib/chart-zoom";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type LogicalRange,
  type AutoscaleInfoProvider,
} from "lightweight-charts";

import {
  formatShanghaiChartTime,
  toIntradayLineData,
} from "@/lib/intraday-source-state";
import { formatIntradayPercent } from "@/lib/intraday-percent";
import type { IntradayPricePoint } from "@/lib/types/stock";

interface IntradayLineChartProps {
  points: readonly (Pick<IntradayPricePoint, "timestamp" | "close"> & Partial<Pick<IntradayPricePoint,"cumulative_volume" | "cumulative_amount">>)[];
  reference?: MinuteReference | null;
  multiDay?: boolean;
  referenceClose?: number | null;
  zoom?: SemanticZoom;
}

const CHART_THEME = {
  background: "#f8f6f0",
  text: "#69736e",
  grid: "rgba(47, 101, 85, 0.09)",
  border: "rgba(47, 101, 85, 0.18)",
  line: "#2f6555",
  areaTop: "rgba(47, 101, 85, 0.20)",
  areaBottom: "rgba(47, 101, 85, 0.01)",
};

/** 只接收真实分钟价格点；该组件不会构造或暗示 OHLC。 */
export function IntradayLineChart({ points, multiDay = false, zoom, reference, referenceClose = null }: IntradayLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const volumeRef = useRef<HTMLDivElement>(null);
  const amountRef = useRef<HTMLDivElement>(null);
  const activityLegendRef = useRef<HTMLDivElement>(null);
  const activity = useMemo(() => minuteActivityRows(points), [points]);
  const legendRef = useRef<HTMLDivElement>(null);
  const quoteRows = useMemo(() => minuteQuoteRows(points, reference), [points, reference]);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
  const percentSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const baseline = !multiDay && referenceClose !== null && Number.isFinite(referenceClose) && referenceClose > 0 ? referenceClose : null;
  const didFitRef = useRef(false);
  const descriptionId = useId();
  const lineData = useMemo(() => toIntradayLineData(points), [points]);
  const hasData = lineData.length > 0;

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !hasData) return;

    const chart = createChart(container, {
      width: container.clientWidth,
      height: container.clientHeight,
      layout: {
        background: { type: ColorType.Solid, color: CHART_THEME.background },
        textColor: CHART_THEME.text,
        fontFamily: "'Cascadia Code', 'Consolas', monospace",
      },
      localization: {
        timeFormatter: (time: Time) =>
          multiDay ? new Date(Number(time) * 1000).toLocaleString("zh-CN", {timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false}) : formatShanghaiChartTime(Number(time)),
      },
      grid: {
        vertLines: { color: CHART_THEME.grid },
        horzLines: { color: CHART_THEME.grid },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      leftPriceScale: {
        visible: baseline !== null,
        borderColor: CHART_THEME.border,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      rightPriceScale: {
        borderColor: CHART_THEME.border,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderColor: CHART_THEME.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 0,
        fixLeftEdge: true,
        fixRightEdge: true,
        minBarSpacing: 0.1,
        tickMarkFormatter: (time: Time) =>
          multiDay ? new Date(Number(time) * 1000).toLocaleDateString("zh-CN", {timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit"}) : formatShanghaiChartTime(Number(time)),
      },
      handleScroll: { vertTouchDrag: false, mouseWheel: false },
      // Keep both independently formatted scales on the same linear range.
      handleScale: { mouseWheel: false, axisPressedMouseMove: { price: false, time: true } },
    });

    const autoscaleInfoProvider: AutoscaleInfoProvider = (original) => {
      const info = original();
      if (!info || baseline === null) return info;
      return { ...info, priceRange: {
        minValue: Math.min(info.priceRange.minValue, baseline),
        maxValue: Math.max(info.priceRange.maxValue, baseline),
      } };
    };
    const series = chart.addAreaSeries({
      priceScaleId: "right",
      autoscaleInfoProvider,
      lineColor: CHART_THEME.line,
      topColor: CHART_THEME.areaTop,
      bottomColor: CHART_THEME.areaBottom,
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    if (baseline !== null) {
      // Identical raw values/range/margins: only the left label formatter differs.
      const percentSeries = chart.addLineSeries({
        priceScaleId: "left", color: CHART_THEME.line, lineVisible: false, crosshairMarkerVisible: false,
        priceLineVisible: false, lastValueVisible: true, autoscaleInfoProvider,
        priceFormat: { type: "custom", minMove: 0.01,
          formatter: (price: number) => formatIntradayPercent(price, baseline) },
      });
      percentSeriesRef.current = percentSeries;
      series.createPriceLine({ price: baseline, color: CHART_THEME.text,
        lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: "昨收" });
      percentSeries.createPriceLine({ price: baseline, color: CHART_THEME.text,
        lineVisible: false, axisLabelVisible: true, title: "" });
    }
    const observer = new ResizeObserver(() => {
      chart.applyOptions({ width: container.clientWidth });
    });
    observer.observe(container);
    chartRef.current = chart;
    seriesRef.current = series;

    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
      percentSeriesRef.current = null;
      didFitRef.current = false;
    };
  }, [hasData, multiDay, zoom, baseline]);

  useEffect(() => {
    const series = seriesRef.current;
    const chart = chartRef.current;
    if (!series || !chart) return;
    series.setData(
      lineData.map((point) => ({
        time: point.time as Time,
        value: point.value,
      })),
    );
    percentSeriesRef.current?.setData(lineData.map(point => ({ time: point.time as Time, value: point.value })));
    if (multiDay) {
      const seen = new Set<string>();
      series.setMarkers(lineData.filter(point => {
        const day = new Date(point.time * 1000).toLocaleDateString("en-CA", {timeZone: "Asia/Shanghai"});
        if (seen.has(day)) return false;
        seen.add(day); return true;
      }).map(point => ({time: point.time as Time, position: "aboveBar", color: CHART_THEME.line,
        shape: "circle", text: new Date(point.time * 1000).toLocaleDateString("zh-CN", {timeZone: "Asia/Shanghai", month: "2-digit", day: "2-digit"}), size: 0.5})));
    }
    if (!didFitRef.current) {
      chart.timeScale().fitContent();
      didFitRef.current = true;
    }
  }, [lineData, multiDay, zoom, baseline]);

  useEffect(() => {
    if (!chartRef.current || !containerRef.current || !zoom || !lineData.length) return;
    return bindChartZoom(chartRef.current, lineData.length, zoom);
  }, [lineData, zoom, baseline]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !quoteRows.length) return;
    const byTime = new Map(quoteRows.map(row => [row.time,row]));
    const update = (time?: Time) => {
      const row = (time == null ? undefined : byTime.get(Number(time))) ?? quoteRows.at(-1)!;
      const signed = (value:number) => `${value>0?"+":""}${value.toFixed(2)}`;
      const fields: Record<string,string> = {
        time: new Date(row.time*1000).toLocaleString("zh-CN",{timeZone:"Asia/Shanghai",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit",hour12:false}),
        price:row.price.toFixed(2), high:row.high.toFixed(2), low:row.low.toFixed(2),
        change:row.amount===null||row.percent===null?"涨跌幅 —":`${signed(row.amount)} 元 (${signed(row.percent)}%)`,
        baseline:row.previous===null?"缺少该交易日前收盘价":`较前收 ${row.previous.toFixed(2)} · ${reference?.source==="sina"?"新浪":reference?.source==="eastmoney"?"东方财富":"报价源"}`,
        volume:row.volume===null?"—":row.volume.toLocaleString("zh-CN",{maximumFractionDigits:0}),
      };
      legendRef.current?.querySelectorAll<HTMLElement>("[data-minute-field]").forEach(slot=>{slot.textContent=fields[slot.dataset.minuteField!]??"—";});
      const badge=legendRef.current?.querySelector<HTMLElement>("[data-minute-change]");
      if(badge){badge.style.color=row.amount===null||row.amount===0?"#68736e":row.amount>0?"#2f7d5a":"#b34b43";}
    };
    update();
    const move = (event:{time?:Time}) => update(event.time);
    chart.subscribeCrosshairMove(move);
    return () => chart.unsubscribeCrosshairMove(move);
  },[quoteRows,multiDay,zoom,reference,baseline]);

  useEffect(() => {
    const main = chartRef.current, price = seriesRef.current;
    if (multiDay || !main || !price || !volumeRef.current || !amountRef.current) return;
    const containers = [volumeRef.current, amountRef.current];
    const keys = ["volume", "turnover"] as const;
    const charts = containers.map((container) => createChart(container, {
      width: container.clientWidth, height: 130,
      layout: { background: { type: ColorType.Solid, color: CHART_THEME.background }, textColor: CHART_THEME.text },
      grid: { vertLines: { color: CHART_THEME.grid }, horzLines: { color: CHART_THEME.grid } },
      rightPriceScale: { minimumWidth: 65, borderColor: CHART_THEME.border },
      timeScale: { timeVisible: true, secondsVisible: false, minBarSpacing: 0.1,
        tickMarkFormatter: (time: Time) => formatShanghaiChartTime(Number(time)) },
      localization: { timeFormatter: (time: Time) => formatShanghaiChartTime(Number(time)) },
      handleScroll: { mouseWheel: false, vertTouchDrag: false }, handleScale: { mouseWheel: false },
    }));
    main.applyOptions({ rightPriceScale: { minimumWidth: 65 } });
    const series = charts.map((chart, i) => {
      const histogram = chart.addHistogramSeries({ priceFormat: { type: "volume" } });
      histogram.setData(activity.map(row => row[keys[i]] === null ? { time: row.time as Time } :
        { time: row.time as Time, value: row[keys[i]]!, color: row.color }));
      return histogram;
    });
    const all = [main, ...charts];
    let syncing = false;
    const rangeHandlers = all.map((chart, index) => {
      const handler = (range: LogicalRange | null) => {
        if (syncing || !range) return;
        syncing = true;
        all.forEach((other, j) => { if (j !== index) other.timeScale().setVisibleLogicalRange(range); });
        syncing = false;
      };
      chart.timeScale().subscribeVisibleLogicalRangeChange(handler);
      return handler;
    });
    const crossHandlers = all.map((chart, index) => {
      const handler = (event: { time?: Time }) => {
        if (syncing) return;
        syncing = true;
        const row = activity.find(row => row.time === Number(event.time));
        const selected = row ?? activity.at(-1);
        if (activityLegendRef.current && selected) activityLegendRef.current.textContent =
          `${formatShanghaiChartTime(selected.time)} · 每分钟成交量 ${selected.volume?.toLocaleString("zh-CN") ?? "—"} 股 · 成交额 ${selected.turnover?.toLocaleString("zh-CN", { maximumFractionDigits: 2 }) ?? "—"} 元`;
        all.forEach((other, j) => {
          if (index === j) return;
          const value = j === 0 ? lineData.find(p => p.time === row?.time)?.value : row?.[keys[j - 1]];
          if (row && value != null) other.setCrosshairPosition(value, row.time as Time, j === 0 ? price : series[j - 1]);
          else other.clearCrosshairPosition();
        });
        syncing = false;
      };
      chart.subscribeCrosshairMove(handler);
      return handler;
    });
    const range = main.timeScale().getVisibleLogicalRange();
    if (range) rangeHandlers[0](range);
    crossHandlers[0]({});
    const observer = new ResizeObserver(() => charts.forEach((chart, i) => chart.applyOptions({ width: containers[i].clientWidth })));
    containers.forEach(container => observer.observe(container));
    return () => {
      observer.disconnect();
      all.forEach((chart, i) => {
        chart.timeScale().unsubscribeVisibleLogicalRangeChange(rangeHandlers[i]);
        chart.unsubscribeCrosshairMove(crossHandlers[i]);
      });
      charts.forEach(chart => chart.remove());
    };
  }, [activity, lineData, multiDay, zoom, baseline]);

  if (lineData.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-md border border-bg-tertiary bg-bg-primary text-sm text-text-muted">
        暂无有效分钟价格点
      </div>
    );
  }

  return (
    <>
      <div className="flex justify-end mb-2"><button className="text-xs text-accent-blue hover:underline" onClick={() => zoom?.controls.current ? zoom.controls.current.reset() : chartRef.current?.timeScale().fitContent()}>适应全部数据</button></div>
      <div ref={legendRef} aria-label={multiDay ? "五日分时行情栏" : "当日分时行情栏"} className="rounded-t-md border border-b-0 border-bg-tertiary bg-bg-primary/50 px-4 pt-3 pb-3">
        <div className="flex justify-between gap-3 text-xs text-text-muted"><span>{multiDay?"五日分时行情":"当日分时行情"}</span><span className="font-number tabular-nums" data-minute-field="time" /> <span>北京时间</span></div>
        <div className="my-3 flex flex-wrap items-end justify-between gap-3">
          <div><div className="mb-1 text-[11px] text-text-muted">分钟价格 / 元</div><span data-minute-field="price" className="font-number text-[28px] font-semibold leading-none tabular-nums" /></div>
          <div data-minute-change className="rounded-md bg-bg-tertiary/50 px-2.5 py-1.5 text-right"><div data-minute-field="change" className="font-number text-sm font-semibold tabular-nums" /><div data-minute-field="baseline" className="mt-0.5 text-[10px]" /></div>
        </div>
        <div className="grid grid-cols-3 gap-3 border-t border-bg-tertiary pt-2.5">
          {([["high","区间最高"],["low","区间最低"],["volume","累计量 / 股"]] as const).map(([key,label])=><div key={key}><div className="mb-1 text-[11px] text-text-muted">{label}</div><div data-minute-field={key} className="font-number text-sm tabular-nums" /></div>)}
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-text-muted">区间为所选交易日已返回的首个点至所选分钟，非完整日高低。缺少前收或成交量时显示 —；跨日不沿用同一个前收。</p>
      </div>
      {!multiDay && <div className="mb-2 flex flex-wrap justify-between gap-2 text-xs text-text-muted">
        <span>{baseline !== null ? `涨跌幅（%）· 昨收 ${baseline.toFixed(2)} 元为 0%` : "涨跌幅基准缺失：未取得与分时同交易日的有效昨收"}</span>
        <span>价格（元）</span>
      </div>}
      <div
        ref={containerRef}
        className="h-72 w-full overflow-hidden rounded-b-md border border-bg-tertiary bg-[#f8f6f0]"
        role="img"
        aria-label={multiDay ? "五日分时连续折线图" : "盘中价格折线图"}
        aria-describedby={descriptionId}
      />
      {!multiDay && <section aria-label="分时成交指标" className="mt-3 rounded-md border border-bg-tertiary overflow-hidden">
        <div className="px-3 py-2 text-xs text-text-muted" ref={activityLegendRef} />
        <h4 className="px-3 text-sm font-medium">每分钟成交量 · 股</h4>
        <div ref={volumeRef} role="img" aria-label="每分钟成交量柱状图" />
        <h4 className="px-3 pt-2 text-sm font-medium border-t border-bg-tertiary">每分钟成交额 · 元</h4>
        <div ref={amountRef} role="img" aria-label="每分钟成交额柱状图" />
        <p className="px-3 py-2 text-xs text-text-muted">由相邻分钟累计值相减；首点、缺失分钟或累计值回退处留空。柱色表示价格较上一分钟涨跌，不代表资金流入流出。</p>
      </section>}
      <p id={descriptionId} className="sr-only">
        {`从 ${formatShanghaiChartTime(lineData[0].time)} 到 ${formatShanghaiChartTime(lineData.at(-1)!.time)}，共 ${lineData.length} 个分钟价格点；最低 ${Math.min(...lineData.map((point) => point.value)).toFixed(2)}，最高 ${Math.max(...lineData.map((point) => point.value)).toFixed(2)}，最新 ${lineData.at(-1)!.value.toFixed(2)}。`}
      </p>
    </>
  );
}
