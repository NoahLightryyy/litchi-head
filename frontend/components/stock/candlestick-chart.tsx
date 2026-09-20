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
  data: Pick<KLineData, "date" | "open" | "high" | "low" | "close" | "volume">[];
}

/** 暖白研究终端配色（匹配全局数据面板） */
const THEME = {
  background: "#f8f6f0",
  textColor: "#68736e",
  gridColor: "#ddd8cd",
  borderColor: "#d8d0c2",
  candleUp: "#2f7d5a",
  candleDown: "#b34b43",
  volumeUp: "rgba(47, 125, 90, 0.24)",
  volumeDown: "rgba(179, 75, 67, 0.22)",
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
        vertLines: { visible: false },
        horzLines: { color: "rgba(104, 115, 110, 0.12)" },
      },
      crosshair: { mode: CrosshairMode.Magnet },
      rightPriceScale: {
        borderColor: THEME.borderColor,
        scaleMargins: { top: 0.08, bottom: 0.25 },
      },
      timeScale: {
        borderColor: THEME.borderColor,
        timeVisible: false,
        secondsVisible: false,
        rightOffset: 2,
        fixLeftEdge: true,
        fixRightEdge: true,
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
      priceLineVisible: false,
      lastValueVisible: false,
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

    // Fit the actual returned window rather than leaving 6px default bars at the right.
    chart.timeScale().fitContent();

    // ── 自适应宽度 ──────────────────────────────────────────
    const handleResize = () => {
      if (container) {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
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
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs text-text-muted">
        <span>价格（元） · 下方为成交量（股）</span>
        <button className="rounded border border-bg-tertiary px-2 py-1 hover:bg-bg-tertiary" onClick={() => chartRef.current?.timeScale().fitContent()}>适应全部数据</button>
      </div>
      <div ref={containerRef} className="w-full h-[360px] sm:h-[420px] rounded-md overflow-hidden" />
    </div>
  );
}
