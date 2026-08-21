"use client";

import { useEffect, useId, useMemo, useRef } from "react";
import {
  ColorType,
  CrosshairMode,
  createChart,
  type IChartApi,
  type ISeriesApi,
  type Time,
} from "lightweight-charts";

import {
  formatShanghaiChartTime,
  toIntradayLineData,
} from "@/lib/intraday-source-state";
import type { IntradayPricePoint } from "@/lib/types/stock";

interface IntradayLineChartProps {
  points: readonly IntradayPricePoint[];
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
export function IntradayLineChart({ points }: IntradayLineChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Area"> | null>(null);
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
        priceFormatter: (price: number) => price.toFixed(2),
        timeFormatter: (time: Time) =>
          formatShanghaiChartTime(Number(time)),
      },
      grid: {
        vertLines: { color: CHART_THEME.grid },
        horzLines: { color: CHART_THEME.grid },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: {
        borderColor: CHART_THEME.border,
        scaleMargins: { top: 0.12, bottom: 0.12 },
      },
      timeScale: {
        borderColor: CHART_THEME.border,
        timeVisible: true,
        secondsVisible: false,
        rightOffset: 2,
        tickMarkFormatter: (time: Time) =>
          formatShanghaiChartTime(Number(time)),
      },
      handleScroll: { vertTouchDrag: false },
    });

    const series = chart.addAreaSeries({
      lineColor: CHART_THEME.line,
      topColor: CHART_THEME.areaTop,
      bottomColor: CHART_THEME.areaBottom,
      lineWidth: 2,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
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
      didFitRef.current = false;
    };
  }, [hasData]);

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
    if (!didFitRef.current) {
      chart.timeScale().fitContent();
      didFitRef.current = true;
    }
  }, [lineData]);

  if (lineData.length === 0) {
    return (
      <div className="flex h-72 items-center justify-center rounded-md border border-bg-tertiary bg-bg-primary text-sm text-text-muted">
        暂无有效分钟价格点
      </div>
    );
  }

  return (
    <>
      <div
        ref={containerRef}
        className="h-72 w-full overflow-hidden rounded-md border border-bg-tertiary bg-[#f8f6f0]"
        role="img"
        aria-label="盘中价格折线图"
        aria-describedby={descriptionId}
      />
      <p id={descriptionId} className="sr-only">
        {`从 ${formatShanghaiChartTime(lineData[0].time)} 到 ${formatShanghaiChartTime(lineData.at(-1)!.time)}，共 ${lineData.length} 个分钟价格点；最低 ${Math.min(...lineData.map((point) => point.value)).toFixed(2)}，最高 ${Math.max(...lineData.map((point) => point.value)).toFixed(2)}，最新 ${lineData.at(-1)!.value.toFixed(2)}。`}
      </p>
    </>
  );
}
