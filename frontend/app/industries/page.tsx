"use client";

import { useState } from "react";
import { useSectors } from "@/lib/hooks/use-market";
import { SectorRanking } from "@/components/macro/sector-ranking";

export default function IndustriesPage() {
  const [sort, setSort] = useState("fund_flow");
  const [category, setCategory] = useState("all");
  const query = useSectors(sort);
  const sectors = query.data?.data ?? [];
  const failedCategories = query.data?.meta.failed_sources ?? [];
  const categories = [{ id: "all", label: "全部板块" }, { id: "industry", label: "行业" }, { id: "concept", label: "概念" }];
  const filtered = category === "all" ? sectors : sectors.filter((sector) => sector.category === category);

  return <div className="mx-auto max-w-7xl space-y-6">
    <div>
      <h1 className="text-2xl font-semibold text-text-primary">行业研究</h1>
      <p className="mt-2 text-sm text-text-muted">浏览行业与概念板块，查看行情、成分股及已收录的产业结构资料。</p>
    </div>
    <div className="flex flex-wrap items-center gap-2" aria-label="板块分类">
      {categories.map((item) => <button key={item.id} type="button" aria-pressed={category === item.id}
        onClick={() => setCategory(item.id)}
        className={`rounded-lg border px-4 py-2 text-sm focus-visible:outline-2 focus-visible:outline-accent-blue ${category === item.id ? "border-accent-blue bg-accent-blue/10 text-accent-blue" : "border-bg-tertiary bg-bg-secondary text-text-secondary"}`}>
        {item.label}{query.data ? failedCategories.includes(item.id) ? " · 来源异常" : ` · ${item.id === "all" ? sectors.length : sectors.filter((sector) => sector.category === item.id).length}` : ""}
      </button>)}
    </div>
    <SectorRanking key={category} sectors={filtered} loading={query.isLoading} error={query.isError || failedCategories.includes(category)}
      refreshError={query.isError && !!query.data} meta={query.data?.meta}
      onRetry={() => void query.refetch()} onSortChange={setSort} />
    <p className="text-xs text-text-muted">板块分类沿用数据源口径。详情中的产业资料覆盖范围和年份单独标注；当前瓶颈与多维投资研究仍在建设中。</p>
  </div>;
}
