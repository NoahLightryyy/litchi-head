"use client";

import { useEffect, useId, useMemo, useRef } from "react";
import { bindChartZoom, type SemanticZoom } from "@/lib/chart-zoom";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
  type AutoscaleInfoProvider,
} from "lightweight-charts";

import {
  formatShanghaiChartTime,
  toIntradayLineData,
} from "@/lib/intraday-source-state";
import { formatIntradayPercent } from "@/lib/intraday-percent";
import type { IntradayPricePoint } from "@/lib/types/stock";

interface IntradayLineChartProps {
  points: readonly Pick<IntradayPricePoint, "timestamp" | "close">[];
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
export function IntradayLineChart({ points, multiDay = false, zoom, referenceClose = null }: IntradayLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
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
      {!multiDay && <div className="mb-2 flex flex-wrap justify-between gap-2 text-xs text-text-muted">
        <span>{baseline !== null ? `涨跌幅（%）· 昨收 ${baseline.toFixed(2)} 元为 0%` : "涨跌幅基准缺失：未取得与分时同交易日的有效昨收"}</span>
        <span>价格（元）</span>
      </div>}
      <div
        ref={containerRef}
        className="h-72 w-full overflow-hidden rounded-md border border-bg-tertiary bg-[#f8f6f0]"
        role="img"
        aria-label={multiDay ? "五日分时连续折线图" : "盘中价格折线图"}
        aria-describedby={descriptionId}
      />
      <p id={descriptionId} className="sr-only">
        {`从 ${formatShanghaiChartTime(lineData[0].time)} 到 ${formatShanghaiChartTime(lineData.at(-1)!.time)}，共 ${lineData.length} 个分钟价格点；最低 ${Math.min(...lineData.map((point) => point.value)).toFixed(2)}，最高 ${Math.max(...lineData.map((point) => point.value)).toFixed(2)}，最新 ${lineData.at(-1)!.value.toFixed(2)}。`}
      </p>
    </>
  );
}
