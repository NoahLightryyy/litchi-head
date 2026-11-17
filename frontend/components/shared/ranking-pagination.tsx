"use client";

interface RankingPaginationProps {
  label: string;
  view: { page: number; pageCount: number; total: number; start: number; end: number };
  onPage: (page: number) => void;
}

export function RankingPagination({ label, view, onPage }: RankingPaginationProps) {
  if (!view.total) return null;
  const button = "rounded border border-bg-tertiary px-3 py-1.5 text-accent-blue disabled:opacity-40";
  return <nav aria-label={`${label}分页`} className="flex flex-wrap items-center justify-between gap-3 text-sm">
    <span className="text-text-muted" role="status">显示 {view.start}–{view.end} / {view.total} 条 · 每页10条</span>
    <div className="flex items-center gap-3">
      <button type="button" className={button} disabled={view.page === 1} onClick={() => onPage(view.page - 1)}>上一页</button>
      <span className="text-text-muted">第 {view.page} / {view.pageCount} 页</span>
      <button type="button" className={button} disabled={view.page === view.pageCount} onClick={() => onPage(view.page + 1)}>下一页</button>
    </div>
  </nav>;
}
