"use client";

interface SectorHeaderProps {
  name: string;
  changePct: number;
  fundFlow: number;
  heat: "high" | "medium" | "low";
}

/** 板块头部信息：名称 + 涨跌幅 + 资金 + 热度标签 */
export function SectorHeader({ name, changePct, fundFlow, heat }: SectorHeaderProps) {
  const heatLabels = { high: "🔥 热门", medium: "📌 关注", low: "— 平静" };
  const heatColors = { high: "bg-accent-green/10 text-accent-green", medium: "bg-accent-gold/10 text-accent-gold", low: "bg-bg-tertiary text-text-muted" };

  return (
    <div className="flex items-center gap-4 flex-wrap">
      <h1 className="text-xl font-bold text-text-primary">{name}</h1>
      <span className={`font-number text-lg ${changePct >= 0 ? "text-accent-green" : "text-accent-red"}`}>
        {changePct >= 0 ? "+" : ""}{changePct.toFixed(2)}%
      </span>
      <span className="text-sm text-text-secondary">
        主力净流入{" "}
        <span className={`font-number ${fundFlow >= 0 ? "text-accent-green" : "text-accent-red"}`}>
          {fundFlow >= 0 ? "+" : ""}{fundFlow.toFixed(1)}亿
        </span>
      </span>
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${heatColors[heat]}`}>
        {heatLabels[heat]}
      </span>
    </div>
  );
}
