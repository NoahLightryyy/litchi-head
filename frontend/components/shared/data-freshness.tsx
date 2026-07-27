"use client";

/** 数据新鲜度标签：显示数据采集时间与距今年限 */
export function DataFreshnessTag({ fetchedAt }: { fetchedAt: string | null }) {
  if (!fetchedAt) return null;

  const ts = new Date(fetchedAt);
  const now = new Date();
  const diffMs = now.getTime() - ts.getTime();
  const diffSec = Math.floor(diffMs / 1000);

  let freshness: string;
  let colorClass: string;

  if (diffSec < 30) {
    freshness = "刚刚";
    colorClass = "text-accent-green";
  } else if (diffSec < 120) {
    freshness = `${diffSec}秒前`;
    colorClass = "text-accent-green";
  } else if (diffSec < 3600) {
    freshness = `${Math.floor(diffSec / 60)}分钟前`;
    colorClass = "text-text-secondary";
  } else {
    freshness = `${Math.floor(diffSec / 3600)}小时前`;
    colorClass = "text-text-muted";
  }

  const timeStr = ts.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-text-muted">数据时间</span>
      <span className={`text-xs font-number ${colorClass}`}>
        {timeStr} ({freshness})
      </span>
    </div>
  );
}
