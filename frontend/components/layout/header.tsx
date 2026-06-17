"use client";

import { usePathname } from "next/navigation";

/** 顶部栏：面包屑导航 + 状态 */
export function Header() {
  const pathname = usePathname();

  // 从路径生成面包屑
  const segments = pathname.split("/").filter(Boolean);
  const breadcrumbLabels: Record<string, string> = {
    sector: "产业链分析",
    stock: "个股决策",
  };

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-bg-tertiary bg-bg-secondary">
      <div className="flex items-center gap-2 text-sm">
        <a href="/" className="text-text-secondary hover:text-text-primary">
          宏观总览
        </a>
        {segments.map((seg, i) => (
          <span key={seg} className="flex items-center gap-2">
            <span className="text-text-muted">/</span>
            <span className={i === segments.length - 1 ? "text-text-primary font-medium" : "text-text-secondary"}>
              {breadcrumbLabels[seg] || seg}
            </span>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-4">
        <span className="text-xs text-text-muted">数据来源: akshare</span>
      </div>
    </header>
  );
}
