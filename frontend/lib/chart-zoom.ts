import type { IChartApi } from "lightweight-charts";

export type PriceWindow = "intraday" | "five-day" | "daily";
export type ZoomDirection = "in" | "out";
export const PRICE_WINDOWS: PriceWindow[] = ["intraday", "five-day", "daily"];
export function stepPriceWindow(current: PriceWindow, direction: ZoomDirection): PriceWindow {
  const index = PRICE_WINDOWS.indexOf(current) + (direction === "out" ? 1 : -1);
  return PRICE_WINDOWS[Math.max(0, Math.min(2, index))];
}
export interface ZoomControls { step: (direction: ZoomDirection) => void; reset: () => void }
export interface SemanticZoom {
  controls: {current: ZoomControls | null};
  entry: {current: ZoomDirection | null};
  window: PriceWindow;
  onReady: (ready: boolean) => void;
  onOut?: () => void;
  onIn?: () => void;
  inThreshold?: number;
}
interface Range { from: number; to: number }
/** Explicit zoom never consumes wheel input. Preserve the viewed end in history. */
export function nextZoomRange(range: Range, count: number, direction: ZoomDirection,
  inThreshold: number, canIn: boolean, canOut: boolean): Range | ZoomDirection {
  const span = Math.max(1, range.to - range.from + 1);
  if (direction === "out" && span >= count * 0.98 && canOut) return "out";
  const minimum = Math.min(5, count);
  const next = Math.min(count, Math.max(minimum, span * (direction === "out" ? 1.55 : 1 / 1.55)));
  if (direction === "in" && next <= inThreshold && range.to >= count - 2 && canIn) return "in";
  const end = range.to >= count - 2 ? count - 0.5 : Math.max(next - 1, Math.min(count - 1, range.to));
  return {from: Math.max(-0.5, end - next + 1), to: end};
}

/** Register buttons against the live chart; animate only viewport, never prices. */
export function bindChartZoom(chart: IChartApi, count: number, zoom: SemanticZoom) {
  let frame = 0, switching = false;
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const animate = (target: Range) => {
    cancelAnimationFrame(frame);
    const start = chart.timeScale().getVisibleLogicalRange();
    if (!start || reduced) { chart.timeScale().setVisibleLogicalRange(target); return; }
    const since = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - since) / 180), ease = 1 - (1 - t) ** 3;
      chart.timeScale().setVisibleLogicalRange({from: start.from + (target.from - start.from) * ease,
        to: start.to + (target.to - start.to) * ease});
      if (t < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
  };
  const controls: ZoomControls = {
    step(direction) {
      if (switching) return;
      const range = chart.timeScale().getVisibleLogicalRange();
      if (!range) return;
      const next = nextZoomRange(range, count, direction, zoom.inThreshold ?? 8, !!zoom.onIn, !!zoom.onOut);
      if (typeof next === "string") {
        switching = true;
        cancelAnimationFrame(frame);
        zoom.entry.current = next;
        zoom.onReady(false);
        (next === "in" ? zoom.onIn : zoom.onOut)?.();
      } else animate(next);
    },
    reset() { cancelAnimationFrame(frame); chart.timeScale().fitContent(); },
  };
  // A boundary handoff enters the next dataset near the previous scale, not fully zoomed out.
  if (zoom.entry.current) {
    const direction = zoom.entry.current;
    zoom.entry.current = null;
    const span = direction === "out" ? Math.min(count, zoom.window === "five-day" ? count / 5 * 1.55 : 12) : count;
    const to = count - 0.5;
    chart.timeScale().setVisibleLogicalRange({from: Math.max(-0.5, to - span + 1), to});
  }
  zoom.controls.current = controls;
  zoom.onReady(true);
  return () => {
    cancelAnimationFrame(frame);
    if (zoom.controls.current === controls) { zoom.controls.current = null; zoom.onReady(false); }
  };
}
