"use client";
import { useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api/client";
import { requireThsFundData, thsFundPeriods, thsFundQueryPolicy, type ThsFundPeriod } from "@/lib/ths-fund-rankings";
import { ThsFundRankingContent } from "./ths-fund-ranking-content";

export function ThsFundRanking() {
  const [period, setPeriod] = useState<ThsFundPeriod>("latest");
  const forceRefresh = useRef(false);
  const query = useQuery({
    queryKey: ["discovery", "fund-flow", "ths", period],
    ...thsFundQueryPolicy,
    queryFn: async ({ signal }) => {
      const refresh = forceRefresh.current;
      forceRefresh.current = false;
      const result = await api.getRaw<unknown>("/discovery/fund-flow/ths", { period, refresh: String(refresh) }, { signal });
      return requireThsFundData(result, period);
    },
  });
  return <section aria-label="资金流入排行" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4 space-y-3">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="font-semibold">资金流入排行</h2>
      <button disabled={query.isFetching || query.isPaused} onClick={() => { forceRefresh.current = true; void query.refetch(); }} className="text-sm text-accent-blue disabled:opacity-50">
        {query.isFetching ? "正在读取…" : "刷新榜单"}
      </button>
    </div>
    <label className="block text-sm">统计周期<select aria-label="同花顺资金净流入统计周期" value={period} onChange={event => setPeriod(event.target.value as ThsFundPeriod)} className="ml-2 rounded border border-bg-tertiary bg-bg-primary p-2">
      {thsFundPeriods.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></label>
    <ThsFundRankingContent key={period} data={query.data} pending={query.isPending} failed={query.isError} paused={query.isPaused} />
  </section>;
}
