import type { IChartApi } from "lightweight-charts";

export type PriceWindow = "intraday" | "five-day" | "daily";
export const PRICE_WINDOWS: PriceWindow[] = ["intraday", "five-day", "daily"];
export function stepPriceWindow(current: PriceWindow, direction: "in" | "out"): PriceWindow {
  const index = PRICE_WINDOWS.indexOf(current) + (direction === "out" ? 1 : -1);
  return PRICE_WINDOWS[Math.max(0, Math.min(2, index))];
}
export interface ZoomGesture { lastEvent: number; switched: boolean; overscroll: number }
export function boundaryIntent(gate: ZoomGesture, delta: number, now: number): boolean {
  if (now - gate.lastEvent > 250) { gate.switched = false; gate.overscroll = 0; }
  gate.lastEvent = now;
  return !gate.switched && delta !== 0;
}
export interface SemanticZoom {
  gesture: {current: ZoomGesture};
  onOut?: () => void;
  onIn?: () => void;
  inThreshold?: number;
}

/** Keep all scaling inside actual data; a continuous wheel gesture changes level at most once. */
export function bindChartZoom(chart: IChartApi, element: HTMLElement, count: number, zoom: SemanticZoom) {
  const wheel = (event: WheelEvent) => {
    if (!event.deltaY || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
    event.preventDefault();
    event.stopPropagation();
    const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? element.clientHeight : 1);
    if (!boundaryIntent(zoom.gesture.current, delta, performance.now())) return;
    const range = chart.timeScale().getVisibleLogicalRange();
    if (!range) return;
    const span = Math.max(1, range.to - range.from + 1);
    if (delta > 0 && span >= count * 0.98) {
      zoom.gesture.current.overscroll += delta;
      if (zoom.onOut && zoom.gesture.current.overscroll >= 100) {
        zoom.gesture.current.switched = true;
        zoom.onOut();
      } else chart.timeScale().fitContent();
      return;
    }
    zoom.gesture.current.overscroll = 0;
    const next = Math.min(count, Math.max(5, span * Math.exp(Math.max(-150, Math.min(150, delta)) * 0.003)));
    if (delta < 0 && next <= (zoom.inThreshold ?? 8) && range.to >= count - 2 && zoom.onIn) {
      zoom.gesture.current.switched = true;
      zoom.onIn();
      return;
    }
    // Keep a latest-window zoom anchored to the last candle, including its half-bar.
    // Otherwise fitContent/edge rounding can progressively move the end into history.
    const end = range.to >= count - 2 ? count - 0.5 : Math.max(next - 1, Math.min(count - 1, range.to));
    chart.timeScale().setVisibleLogicalRange({from: Math.max(0, end - next + 1), to: end});
  };
  element.addEventListener("wheel", wheel, {passive: false, capture: true});
  return () => element.removeEventListener("wheel", wheel, {capture: true});
}
