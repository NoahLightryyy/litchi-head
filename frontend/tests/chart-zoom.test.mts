import type { IChartApi } from "lightweight-charts";
import assert from "node:assert/strict";
import test from "node:test";
import { nextZoomRange, stepPriceWindow, bindChartZoom, type ZoomControls } from "../lib/chart-zoom.ts";
import { parseFiveDay } from "../lib/five-day-display.ts";

test("时间层级双向切换并在两端停止", () => {
  assert.equal(stepPriceWindow("intraday", "out"), "five-day");
  assert.equal(stepPriceWindow("five-day", "out"), "daily");
  assert.equal(stepPriceWindow("daily", "out"), "daily");
  assert.equal(stepPriceWindow("daily", "in"), "five-day");
  assert.equal(stepPriceWindow("five-day", "in"), "intraday");
  assert.equal(stepPriceWindow("intraday", "in"), "intraday");
});
test("按钮连续缩放，到边界才换层；历史位置不跳到最新日", () => {
  assert.equal(nextZoomRange({from:0,to:99},100,"out",8,true,true), "out");
  assert.equal(nextZoomRange({from:90,to:99},100,"in",8,true,true), "in");
  const old = nextZoomRange({from:10,to:19},100,"in",8,true,true);
  assert.equal(typeof old,"object");
  if (typeof old === "object") assert.equal(old.to,19);
  const edge=nextZoomRange({from:0,to:98.5},100,"in",8,true,true);
  if(typeof edge === "object") { assert.equal(edge.to,99.5); assert.ok(edge.from>0); }
  const end=nextZoomRange({from:0,to:99},100,"out",8,false,false);
  if(typeof end === "object") assert.ok(end.from>=-0.5 && end.to<=99.5);
});

test("控制器动画、边界防重复切换、入场尺度和卸载清理", () => {
  const originals = ["window","requestAnimationFrame","cancelAnimationFrame"].map(k=>[k,Object.getOwnPropertyDescriptor(globalThis,k)] as const);
  let frame: FrameRequestCallback | null=null;
  Object.defineProperty(globalThis,"window",{configurable:true,value:{matchMedia:()=>({matches:false})}});
  Object.defineProperty(globalThis,"requestAnimationFrame",{configurable:true,value:(f:FrameRequestCallback)=>{frame=f;return 1;}});
  Object.defineProperty(globalThis,"cancelAnimationFrame",{configurable:true,value:()=>{frame=null;}});
  try {
    let range={from:0,to:99}, out=0, ready=false;
    const chart={timeScale:()=>({getVisibleLogicalRange:()=>range,setVisibleLogicalRange:(v:typeof range)=>{range=v;},fitContent:()=>{range={from:0,to:99};}})};
    const controls:{current:ZoomControls|null}={current:null};
    const zoom={controls,entry:{current:null},window:"five-day" as const,onReady:(r:boolean)=>{ready=r;},onOut:()=>{out++;}};
    const cleanup=bindChartZoom(chart as unknown as IChartApi,100,zoom);
    assert.equal(ready,true);
    controls.current!.step("in");
    assert.equal(range.from,0);
    assert.ok(frame);
    (frame as FrameRequestCallback)(performance.now()+200);
    assert.ok(range.from>0);
    controls.current!.reset();
    controls.current!.step("out");controls.current!.step("out");
    assert.equal(out,1);assert.equal(ready,false);
    cleanup();assert.equal(controls.current,null);assert.equal(frame,null);
    const cleanupNext=bindChartZoom(chart as unknown as IChartApi,100,zoom);
    assert.ok(range.to-range.from<50);
    cleanupNext();
  } finally {
    for(const [key,descriptor] of originals) {if(descriptor) Object.defineProperty(globalThis,key,descriptor);else Reflect.deleteProperty(globalThis,key);}
  }
});

test("五日契约拒绝错股票、重复点、缺交易日身份和冒充已核验", () => {
  const v = {symbol: "300199", source: "tencent", price_basis: "unverified_raw", verification: "single_source",
    status: "partial", fetched_at: "2026-10-01T10:00:00+08:00", days: ["2026-09-30"],
    points: [{timestamp: "2026-09-30T09:30:00+08:00", close: 23}], incomplete_days: ["2026-09-30"], missing_days: [], error_code: null};
  assert.equal(parseFiveDay(v, "300199").points.length, 1);
  for (const bad of [{...v, symbol: "000001"}, {...v, points: [...v.points, ...v.points]},
    {...v, days: []}, {...v, verification: "verified"}, {...v, points: [{...v.points[0], close: NaN}]}]) {
    assert.throws(() => parseFiveDay(bad, "300199"));
  }
});
