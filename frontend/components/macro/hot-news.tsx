"use client";

interface HotNewsProps {
  items?: Array<{ title: string; time: string; url?: string }>;
  loading?: boolean;
}

/** 热点快讯滚动条 */
export function HotNews({ items, loading }: HotNewsProps) {
  if (loading) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
        <div className="h-3 w-20 bg-bg-tertiary rounded animate-pulse" />
      </div>
    );
  }

  if (!items || items.length === 0) {
    return (
      <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
        <h3 className="text-sm font-semibold text-text-primary mb-3">热点快讯</h3>
        <p className="text-xs text-text-muted text-center py-4">暂无实时快讯（待接入数据源）</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-text-primary">热点快讯</h3>
        <span className="text-xs text-text-muted">实时</span>
      </div>
      <div className="space-y-2">
        {items.map((item, i) => (
          <div key={i} className="flex items-start gap-2 text-sm">
            <span className="w-1.5 h-1.5 rounded-full bg-accent-blue mt-1.5 shrink-0" />
            <span className="text-text-secondary flex-1">{item.title}</span>
            <span className="text-xs text-text-muted whitespace-nowrap">{item.time}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
