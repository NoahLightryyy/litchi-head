"use client";

import type { NewsItem } from "@/lib/types/stock";

interface NewsFeedProps {
  items: NewsItem[];
  loading?: boolean;
  code: string;
}

/** 关联新闻流 */
export function NewsFeed({ items, loading, code }: NewsFeedProps) {
  return (
    <div className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5">
      <h2 className="text-sm font-semibold text-text-primary mb-3">关联新闻</h2>

      {loading ? (
        <div className="space-y-2 animate-pulse">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-10 bg-bg-tertiary rounded" />
          ))}
        </div>
      ) : items.length > 0 ? (
        <div className="space-y-2">
          {items.map((n, i) => (
            <a
              key={i}
              href={n.url}
              target="_blank"
              rel="noopener noreferrer"
              className="block p-3 rounded-md bg-bg-primary/50 border border-bg-tertiary hover:border-bg-elevated transition-colors"
            >
              <div className="text-sm text-text-primary">{n.title}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-text-muted">{n.source}</span>
                <span className="text-xs text-text-muted">·</span>
                <span className="text-xs text-text-muted">{n.date}</span>
              </div>
            </a>
          ))}
        </div>
      ) : (
        <p className="text-xs text-text-muted text-center py-4">暂无关联新闻</p>
      )}
    </div>
  );
}
