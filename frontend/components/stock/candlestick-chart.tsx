"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  IChartApi,
  ISeriesApi,
  ColorType,
  CrosshairMode,
} from "lightweight-charts";
import type { KLineData } from "@/lib/types/stock";

interface CandlestickChartProps {
  data: KLineData[];
}

/** 暗色主题配色（匹配 Tailwind bg-bg-secondary / bg-bg-primary） */
const THEME = {
  background: "#141420",
  textColor: "#8b8fa3",
  gridColor: "#2a2a3e",
  borderColor: "#2a2a3e",
  candleUp: "#26a69a",
  candleDown: "#ef5350",
  volumeUp: "rgba(38, 166, 154, 0.3)",
  volumeDown: "rgba(239, 83, 80, 0.3)",
};

/**
 * 轻量级 K 线渲染组件
 *
 * 封装 TradingView Lightweight Charts，纯渲染层。
 * 不负责数据获取 — 数据由父组件传入。
 */
export function CandlestickChart({ data }: CandlestickChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  useEffect(() => {
    if (!containerRef.current || data.length === 0) return;

    const container = containerRef.current;
    const { clientWidth: width, clientHeight: height } = container;

    // ── 创建图表 ────────────────────────────────────────────
    const chart = createChart(container, {
      width,
      height,
      layout: {
        background: { type: ColorType.Solid, color: THEME.background },
        textColor: THEME.textColor,
      },
      grid: {
        vertLines: { color: THEME.gridColor },
        horzLines: { color: THEME.gridColor },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: {
        borderColor: THEME.borderColor,
        scaleMargins: { top: 0.05, bottom: 0.25 },
      },
      timeScale: {
        borderColor: THEME.borderColor,
        timeVisible: false,
        secondsVisible: false,
      },
      handleScroll: { vertTouchDrag: false },
    });

    // ── K 线序列 ────────────────────────────────────────────
    const candleSeries = chart.addCandlestickSeries({
      upColor: THEME.candleUp,
      downColor: THEME.candleDown,
      borderUpColor: THEME.candleUp,
      borderDownColor: THEME.candleDown,
      wickUpColor: THEME.candleUp,
      wickDownColor: THEME.candleDown,
      priceFormat: { type: "price", precision: 2, minMove: 0.01 },
    });
    candleSeries.setData(
      data.map((d) => ({
        time: d.date as unknown as import("lightweight-charts").Time,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
      })),
    );

    // ── 成交量直方图（下方子图） ──────────────────────────────
    const volumeSeries = chart.addHistogramSeries({
      color: THEME.volumeUp,
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    volumeSeries.setData(
      data.map((d) => ({
        time: d.date as unknown as import("lightweight-charts").Time,
        value: d.volume,
        color: d.close >= d.open ? THEME.volumeUp : THEME.volumeDown,
      })),
    );

    // ── 自适应宽度 ──────────────────────────────────────────
    const handleResize = () => {
      if (container) {
        chart.applyOptions({ width: container.clientWidth });
      }
    };
    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // ── 清理 ──────────────────────────────────────────────
    return () => {
      observer.disconnect();
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      volumeSeriesRef.current = null;
    };
  }, [data]);

  return (
    <div
      ref={containerRef}
      className="w-full h-80 rounded-md overflow-hidden"
    />
  );
}
