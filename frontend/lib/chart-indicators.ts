/** Deterministic chart indicators, always calculated from the exact plotted candles. */
export interface CandleInput {date: string; open: number; high: number; low: number; close: number; volume: number}
export type Value = number | null;
export function sma(values: number[], period: number): Value[] {
  return values.map((_, i) => i + 1 < period ? null : values.slice(i + 1 - period, i + 1).reduce((a,b) => a+b,0)/period);
}
function ema(values: number[], period: number): Value[] {
  const result: Value[] = values.map(() => null);
  if (values.length < period) return result;
  let value = values.slice(0,period).reduce((a,b) => a+b,0)/period;
  result[period-1] = value;
  for(let i=period;i<values.length;i++) {value += (values[i]-value)*2/(period+1); result[i]=value;}
  return result;
}
export function chartIndicators(rows: CandleInput[]) {
  const closes = rows.map(r=>r.close), n=rows.length;
  const fast=ema(closes,12), slow=ema(closes,26);
  const dif=closes.map((_,i)=>fast[i] == null || slow[i] == null ? null : fast[i]! - slow[i]!);
  const signal=ema(dif.filter((v):v is number=>v!==null),9);
  const dea=dif.map((v,i)=>v === null ? null : signal[i-25] ?? null);
  const histogram=dif.map((v,i)=>v===null || dea[i]===null ? null : v-dea[i]!);
  const rsi:Value[]=Array(n).fill(null), k:Value[]=Array(n).fill(null), d:Value[]=Array(n).fill(null), j:Value[]=Array(n).fill(null);
  let gain=0,loss=0,prevK=50,prevD=50;
  for(let i=1;i<n;i++) {
    const change=closes[i]-closes[i-1];
    if(i<=14){gain+=Math.max(change,0)/14;loss+=Math.max(-change,0)/14;}
    else {gain=(gain*13+Math.max(change,0))/14;loss=(loss*13+Math.max(-change,0))/14;}
    if(i>=14)rsi[i]=loss===0 ? (gain===0?50:100) : 100-100/(1+gain/loss);
  }
  for(let i=8;i<n;i++) {
    const window=rows.slice(i-8,i+1), hi=Math.max(...window.map(r=>r.high)),lo=Math.min(...window.map(r=>r.low));
    const rsv=hi===lo?50:(closes[i]-lo)/(hi-lo)*100;
    prevK=(2*prevK+rsv)/3;prevD=(2*prevD+prevK)/3;
    k[i]=prevK;d[i]=prevD;j[i]=3*prevK-2*prevD;
  }
  const middle=sma(closes,20),upper=middle.map((v,i)=>v===null?null:v+2*Math.sqrt(closes.slice(i-19,i+1).reduce((s,c)=>s+(c-v)**2,0)/20));
  const lower=middle.map((v,i)=>v===null?null:2*v-upper[i]!);
  return {ma5:sma(closes,5),ma10:sma(closes,10),ma20:middle,ma60:sma(closes,60),dif,dea,histogram,rsi,k,d,j,upper,middle,lower};
}
