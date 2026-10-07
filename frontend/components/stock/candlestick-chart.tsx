"use client";

import { bindChartZoom, type SemanticZoom } from "@/lib/chart-zoom";
import { candleChange, historyRange, historyViewport } from "@/lib/chart-navigation";
import { chartIndicators, type CandleInput, type Value } from "@/lib/chart-indicators";
import { useEffect, useRef, useState } from "react";
import { createChart, ColorType, CrosshairMode, type IChartApi, type ISeriesApi, type LogicalRange, type Time } from "lightweight-charts";

const COLORS = ["#ba8735", "#8762b2", "#277a9a", "#2f7d5a"];
const PANELS = ["MACD", "RSI", "KDJ"] as const;
type Panel = typeof PANELS[number];

/** Vertically aligned panes share dates, zoom and crosshair; no separate price feed. */
export function CandlestickChart({data,zoom,priceUnit="元",volumeLabel="成交量（股）"}: {data:CandleInput[];zoom?:SemanticZoom;priceUnit?:string;volumeLabel?:string}) {
  const root=useRef<HTMLDivElement>(null), charts=useRef<IChartApi[]>([]);
  const slider=useRef<HTMLInputElement>(null), rangeLabel=useRef<HTMLSpanElement>(null);
  const viewport=useRef<{data:CandleInput[];range:LogicalRange|null}|null>(null);
  const [panels,setPanels]=useState<Panel[]>(["MACD","RSI","KDJ"]);
  const [overlay,setOverlay]=useState<"MA"|"BOLL">("MA");
  useEffect(()=>{
    if(!root.current || !data.length)return;
    const indicators=chartIndicators(data);
    const containers=Array.from(root.current.querySelectorAll<HTMLDivElement>("[data-chart-pane]"));
    const legends=Array.from(root.current.querySelectorAll<HTMLDivElement>("[data-chart-legend]"));
    const definitions:{label:string;values:Value[];color:string;hist?:boolean}[][]=[
      (overlay==="MA"?["ma5","ma10","ma20","ma60"] as const:["upper","middle","lower"] as const).map((key,i)=>({label:key.toUpperCase(),values:indicators[key],color:COLORS[i]})),
      [{label:volumeLabel,values:data.map(r=>r.volume),color:COLORS[3],hist:true}],
      ...panels.map(panel=>panel==="MACD"?[
        {label:"柱 DIF−DEA",values:indicators.histogram,color:COLORS[3],hist:true},
        {label:"DIF",values:indicators.dif,color:COLORS[0]}, {label:"DEA",values:indicators.dea,color:COLORS[1]},
      ]:panel==="RSI"?[{label:"RSI14",values:indicators.rsi,color:COLORS[1]}]:[
        {label:"K",values:indicators.k,color:COLORS[0]}, {label:"D",values:indicators.d,color:COLORS[2]}, {label:"J",values:indicators.j,color:COLORS[1]},
      ]),
    ];
    const anchors:ISeriesApi<"Line"|"Candlestick"|"Histogram">[]=[];
    const anchorValues:Value[][]=[];
    const created=containers.map((container,index)=>{
      const chart=createChart(container,{width:container.clientWidth,height:index===0?320:index===1?110:150,
        layout:{background:{type:ColorType.Solid,color:"#f8f6f0"},textColor:"#68736e",fontSize:11},
        grid:{vertLines:{color:"#eae6dc"},horzLines:{color:"#eae6dc"}},
        crosshair:{mode:CrosshairMode.Normal},rightPriceScale:{minimumWidth:76,borderColor:"#d8d0c2"},
        timeScale:{minBarSpacing:0.1,visible:index===containers.length-1,borderColor:"#d8d0c2",rightOffset:0,fixLeftEdge:true,fixRightEdge:true},
        handleScroll:{vertTouchDrag:false,mouseWheel:false},handleScale:{mouseWheel:false},
      });
      if(index===0){
        const candle=chart.addCandlestickSeries({upColor:"#2f7d5a",downColor:"#b34b43",borderVisible:false,wickUpColor:"#2f7d5a",wickDownColor:"#b34b43",lastValueVisible:false,priceLineVisible:false});
        candle.setData(data.map(r=>({...r,time:r.date as Time})));
        anchors.push(candle);anchorValues.push(data.map(r=>r.close));
      }
      definitions[index].forEach((def,j)=>{
        const series=def.hist?chart.addHistogramSeries({priceFormat:{type:index===1?"volume":"price"},lastValueVisible:false,priceLineVisible:false}):chart.addLineSeries({color:def.color,lineWidth:1,lastValueVisible:false,priceLineVisible:false,crosshairMarkerVisible:true});
        series.setData(data.map((r,i)=>def.values[i]===null?{time:r.date as Time}:{time:r.date as Time,value:def.values[i]!,color:def.hist?(index===1?r.close>=r.open:def.values[i]!>=0)?"#2f7d5a":"#b34b43":def.color}));
        if(index>0&&j===0){anchors.push(series);anchorValues.push(def.values);}
        if(index>1 && panels[index-2]==="RSI")for(const price of [30,70])series.createPriceLine({price,color:"#bcb4a5",lineWidth:1,lineStyle:2,axisLabelVisible:false,title:""});
      });
      return chart;
    });
    charts.current=created;
    let syncing=false;
    const updateSlider = (range: {from:number;to:number}) => {
      const view = historyViewport(data.length, range);
      if (slider.current) {
        slider.current.max = String(view.max);
        slider.current.value = String(view.start);
        slider.current.disabled = view.max === 0;
        slider.current.setAttribute("aria-valuetext", `${data[view.start].date} 至 ${data[view.end].date}`);
      }
      updateLegends(view.end);
      if (rangeLabel.current) rangeLabel.current.textContent = `${data[view.start].date} — ${data[view.end].date} · ${view.size} 根${view.max === 0 ? "（已显示全部）" : ""}`;
    };
    const closes = data.map(row => row.close);
    const updateLegends=(i:number)=>legends.forEach((legend,p)=>{
      const change = candleChange(closes, i);
      const signed = (value:number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
      if (p === 0) {
        const fields: Record<string, string> = {
          date: data[i].date, close: data[i].close.toFixed(2),
          open: data[i].open.toFixed(2), high: data[i].high.toFixed(2), low: data[i].low.toFixed(2),
          change: change ? `${signed(change.amount)} ${priceUnit}  (${signed(change.percent)}%)` : "—",
          baseline: change ? "较前一根收盘" : "缺少前收盘价",
        };
        legend.querySelectorAll<HTMLElement>("[data-price-field]").forEach(slot => {
          slot.textContent = fields[slot.dataset.priceField!] ?? "—";
        });
        const badge = legend.querySelector<HTMLElement>("[data-change-badge]");
        if (badge) {
          badge.style.color = change && change.amount > 0 ? "#2f7d5a" : change && change.amount < 0 ? "#b34b43" : "#68736e";
          badge.style.backgroundColor = change && change.amount > 0 ? "rgba(47,125,90,0.08)" : change && change.amount < 0 ? "rgba(179,75,67,0.08)" : "rgba(104,115,110,0.08)";
        }
        legend.querySelectorAll<HTMLElement>("[data-indicator-value]").forEach((slot,index) => {
          slot.textContent = definitions[0][index].values[i]?.toFixed(2) ?? "—";
        });
      } else {
        legend.textContent = `${data[i].date}  ` + definitions[p].map(def =>
          `${def.label} ${p === 1 ? def.values[i]?.toLocaleString("zh-CN", {maximumFractionDigits:0}) ?? "—" : def.values[i]?.toFixed(2) ?? "—"}`
        ).join("   ");
      }
    });
    created.forEach((chart,index)=>{
      chart.timeScale().subscribeVisibleLogicalRangeChange(range=>{
        if(syncing||!range)return;syncing=true;
        updateSlider(range);
        created.forEach((other,j)=>{if(index!==j)other.timeScale().setVisibleLogicalRange(range);});syncing=false;
      });
      chart.subscribeCrosshairMove(param=>{
        if(syncing)return;syncing=true;
        const i=param.time?data.findIndex(r=>r.date===String(param.time)):-1;
        const visible = created[0].timeScale().getVisibleLogicalRange();
        updateLegends(i>=0?i:visible?historyViewport(data.length,visible).end:data.length-1);
        created.forEach((other,j)=>{
          if(j===index)return;
          if(i>=0&&anchorValues[j][i]!==null)other.setCrosshairPosition(anchorValues[j][i]!,data[i].date as Time,anchors[j]);
          else other.clearCrosshairPosition();
        });syncing=false;
      });
    });
    if(viewport.current?.data===data && viewport.current.range)created[0].timeScale().setVisibleLogicalRange(viewport.current.range);
    else created[0].timeScale().setVisibleLogicalRange(historyRange(data.length,0,data.length));
    updateLegends(data.length-1);
    const initialRange = created[0].timeScale().getVisibleLogicalRange();
    if(initialRange) updateSlider(initialRange);
    const unbind=zoom?bindChartZoom(created[0],data.length,zoom):undefined;
    const observer=new ResizeObserver(()=>created.forEach((chart,i)=>chart.applyOptions({width:containers[i].clientWidth})));
    containers.forEach(c=>observer.observe(c));
    return()=>{viewport.current={data,range:created[0].timeScale().getVisibleLogicalRange()};unbind?.();observer.disconnect();created.forEach(chart=>chart.remove());charts.current=[];};
  },[data,panels,overlay,zoom,priceUnit,volumeLabel]);
  return <section aria-label="K线与联动指标" className="space-y-3">
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span className="text-text-muted">主图</span>
      {(["MA","BOLL"] as const).map(name=><button key={name} aria-pressed={overlay===name} onClick={()=>setOverlay(name)} className={`rounded px-2 py-1 ${overlay===name?"bg-accent-blue text-white":"bg-bg-tertiary"}`}>{name}</button>)}
      <span className="ml-2 text-text-muted">副图</span>
      {PANELS.map(name=><button key={name} aria-pressed={panels.includes(name)} onClick={()=>setPanels(current=>current.includes(name)?current.filter(p=>p!==name):PANELS.filter(p=>p===name||current.includes(p)))} className={`rounded px-2 py-1 ${panels.includes(name)?"bg-accent-blue text-white":"bg-bg-tertiary"}`}>{name}</button>)}
      <button className="ml-auto rounded border border-bg-tertiary px-2 py-1" onClick={()=>charts.current[0]?.timeScale().setVisibleLogicalRange(historyRange(data.length,0,data.length))}>适应全部数据</button>
    </div>
    <div className="rounded border border-bg-tertiary bg-bg-primary/50 p-3 text-xs">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <label htmlFor="kline-history-position">历史日期</label>
        <span ref={rangeLabel} className="font-number text-text-muted" />
      </div>
      <input ref={slider} id="kline-history-position" type="range" min="0" max="0" step="1" defaultValue="0"
        className="w-full accent-[var(--color-accent-blue)] disabled:opacity-40" onChange={event=>{
          const chart=charts.current[0], range=chart?.timeScale().getVisibleLogicalRange();
          if(chart&&range)chart.timeScale().setVisibleLogicalRange(historyRange(data.length,Number(event.target.value),historyViewport(data.length,range).size));
        }} />
      <p className="mt-1 text-text-muted">向左查看更早日期，向右查看最近日期；主图和副图一起移动。默认显示全部已取得历史；放大后可滑动，一键“适应全部数据”恢复全览。</p>
    </div>
    <div ref={root} className="overflow-hidden rounded border border-bg-tertiary">
      {[`K线 · ${priceUnit === "点" ? "指数点位" : "价格（元）"}`,"成交量",...panels].map((name,index)=><div key={name} className="border-b border-bg-tertiary last:border-0">
        {index === 0 ? <PriceLegend overlay={overlay} priceUnit={priceUnit} /> : <div className="flex flex-wrap gap-x-3 px-3 py-2 text-xs"><strong>{name}</strong><span data-chart-legend className="font-number text-text-muted" /></div>}
        <div data-chart-pane className="w-full" />
      </div>)}
    </div>
    <details className="text-xs text-text-muted"><summary className="cursor-pointer">指标含义与计算口径</summary>
      <p className="mt-2 leading-relaxed">移动十字线可按日期对照全部图；拖动任一副图同步时间范围。MA（5/10/20/60）观察平均成本趋势；BOLL（20，2倍标准差）观察价格波动范围；RSI（14）观察相对涨跌动量；MACD（12/26/9）比较快慢均线，柱为 DIF−DEA，未乘2；KDJ（9/3/3）观察收盘价在近期高低区间的位置，K/D初值50，J可能超过0–100。预热不足显示空白。涨跌额和涨跌幅按前一根同口径K线收盘价计算，首根缺少前收时留空；未复权数据在除权除息日可能不同于交易所公布涨跌幅。所有指标使用当前图相同周期、相同复权口径的完整序列，缩放不重新取样。指标不是涨跌概率。</p>
    </details>
  </section>;
}


/** Fixed slots keep hover updates smooth without rebuilding the charts. */
function PriceLegend({overlay,priceUnit}: {overlay: "MA" | "BOLL";priceUnit:string}) {
  const labels = overlay === "MA" ? ["MA5", "MA10", "MA20", "MA60"] : ["上轨", "中轨", "下轨"];
  return <div data-chart-legend aria-label="所选K线行情" className="px-4 pt-3 pb-2">
    <div className="flex items-center justify-between gap-3 text-xs">
      <span className="font-medium text-text-secondary">K线行情</span>
      <time data-price-field="date" className="font-number tabular-nums text-text-muted" />
    </div>
    <div className="my-3 flex flex-wrap items-end justify-between gap-3">
      <div>
        <div className="mb-1 text-[11px] text-text-muted">收盘价 <span className="opacity-70">/ {priceUnit}</span></div>
        <span data-price-field="close" className="font-number text-[28px] font-semibold leading-none tracking-tight tabular-nums text-text-primary" />
      </div>
      <div data-change-badge className="rounded-md px-2.5 py-1.5 text-right">
        <div data-price-field="change" className="font-number text-sm font-semibold tabular-nums whitespace-nowrap" />
        <div data-price-field="baseline" className="mt-0.5 text-[10px] opacity-80" />
      </div>
    </div>
    <div className="grid grid-cols-3 gap-3 border-t border-bg-tertiary pt-2.5 pb-3">
      {([ ["open", "开盘"], ["high", "最高"], ["low", "最低"] ] as const).map(([key,label]) => <div key={key}>
        <div className="mb-1 text-[11px] text-text-muted">{label}</div>
        <div data-price-field={key} className="font-number text-sm font-medium tabular-nums text-text-primary" />
      </div>)}
    </div>
    <div className="grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-bg-tertiary pt-2 text-[11px] lg:grid-cols-4">
      {labels.map((label,index) => <span key={label} className="inline-flex items-center gap-1.5 whitespace-nowrap">
        <span className="h-1.5 w-1.5 rounded-full" style={{backgroundColor:COLORS[index]}} />
        <span className="text-text-muted">{label}</span>
        <span data-indicator-value className="font-number font-medium tabular-nums" style={{color:COLORS[index]}} />
      </span>)}
    </div>
  </div>;
}
