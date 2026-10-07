export interface MinuteQuotePoint {timestamp:string;close:number;cumulative_volume?:number}
export interface MinuteReference {fetched_at:string|null;prev_close:number;source?:string}
const dayOf = (timestamp:string) => new Date(Date.parse(timestamp)+8*3600000).toISOString().slice(0,10);
/** Use only a dated reference for this trading day; never reuse today's previous close for older days. */
export function minuteQuoteRows(points:readonly MinuteQuotePoint[], reference?:MinuteReference|null) {
  const unique=new Map<number,MinuteQuotePoint>();
  points.forEach(p=>{const t=Date.parse(p.timestamp);if(Number.isFinite(t)&&Number.isFinite(p.close))unique.set(Math.floor(t/1000),p);});
  let day="", high=0, low=0;
  return [...unique.entries()].sort((a,b)=>a[0]-b[0]).map(([time,p])=>{
    const currentDay=dayOf(p.timestamp);
    if(currentDay!==day){day=currentDay;high=p.close;low=p.close;}
    high=Math.max(high,p.close);low=Math.min(low,p.close);
    const validReference=reference?.fetched_at && Number.isFinite(Date.parse(reference.fetched_at)) &&
      dayOf(reference.fetched_at)===day && Number.isFinite(reference.prev_close) && reference.prev_close>0;
    const previous=validReference?reference!.prev_close:null;
    return {time,price:p.close,high,low,previous,
      amount:previous===null?null:p.close-previous,
      percent:previous===null?null:(p.close/previous-1)*100,
      volume:p.cumulative_volume!=null&&Number.isFinite(p.cumulative_volume)&&p.cumulative_volume>=0?p.cumulative_volume:null};
  });
}

/** Difference only adjacent minutes; gaps, resets and the first sample are unknown. */
export function minuteActivityRows(
  points: readonly (MinuteQuotePoint & { cumulative_amount?: number })[],
) {
  const samples = new Map<number, typeof points[number]>();
  for (const point of points) {
    const time = Date.parse(point.timestamp) / 1000;
    if (Number.isFinite(time) && Number.isFinite(point.close)) samples.set(time, point);
  }
  const ordered = [...samples.entries()].sort((a, b) => a[0] - b[0]);
  return ordered.map(([time, point], index) => {
    const prior = ordered[index - 1];
    const adjacent = prior && time - prior[0] === 60 && dayOf(point.timestamp) === dayOf(prior[1].timestamp);
    const delta = (key: 'cumulative_volume' | 'cumulative_amount'): number | null => {
      const current = point[key], previous = prior?.[1][key];
      if (!adjacent || current == null || previous == null || !Number.isFinite(current) ||
          !Number.isFinite(previous) || previous < 0 || current < previous) return null;
      // Older providers encode an absent amount as zero even with traded shares.
      if (key === 'cumulative_amount' && ((current === 0 && (point.cumulative_volume ?? 0) > 0) ||
          (previous === 0 && (prior[1].cumulative_volume ?? 0) > 0))) return null;
      return current - previous;
    };
    return { time, volume: delta('cumulative_volume'), turnover: delta('cumulative_amount'),
      color: prior && point.close < prior[1].close ? '#b34b43' : '#2f7d5a' };
  });
}
