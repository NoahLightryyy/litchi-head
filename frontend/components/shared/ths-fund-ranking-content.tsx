"use client";
import { useState } from "react";
import Link from "next/link";
import type { ThsFundResult } from "@/lib/ths-fund-rankings";
import { rankingPage } from "@/lib/ranking-page";
import { RankingPagination } from "./ranking-pagination";

export interface ThsFundRankingContentProps {
  data?: ThsFundResult;
  pending: boolean;
  failed: boolean;
  paused: boolean;
}

export function ThsFundRankingContent({ data, pending, failed, paused }: ThsFundRankingContentProps) {
  const [page, setPage] = useState(1);
  const view = rankingPage(data?.data ?? [], page);
  const available = data?.status === "partial" && data.data.length > 0;
  return <>
    <p className="text-sm text-text-muted">来源：同花顺 · 口径：资金净流入 · 数据日期：来源未提供</p>
    {paused ? <p role="status" className="text-sm">网络已断开，恢复连接后将重试。{available ? "保留上次获取的本周期榜单。" : ""}</p>
      : pending ? <p role="status" className="py-4">正在读取同花顺资金榜…</p>
      : failed && <p role="alert" className="text-sm">{available
        ? "刷新未成功，保留上次获取的本周期榜单。"
        : "当前未取得同花顺资金净流入榜，可刷新或展开东方财富榜。"}</p>}
    {available && <>
      <p className="text-xs text-text-muted">采集时间（北京时间）：{new Date(data.fetched_at).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false })}{data.cached ? " · 缓存记录" : ""}</p>
      {data.cached && data.reason && <p role="status" className="text-sm text-text-muted">{data.reason}</p>}
      <details className="text-xs leading-6 text-text-muted">
        <summary className="cursor-pointer">统计口径与范围</summary>
        <p>{data.scope}。采集时间不代表报价时间或统计截止日。负数为净流出，金额为人民币。</p>
      </details>
      <div className="overflow-x-auto"><table className="w-full text-left text-sm">
        <thead><tr className="text-text-muted"><th className="p-2">个股</th><th className="p-2 whitespace-nowrap">资金净流入（万元）</th><th className="p-2 whitespace-nowrap">最新价（元）</th></tr></thead>
        <tbody>{view.items.map(row => <tr key={row.code} className="border-t border-bg-tertiary">
          <td className="p-2"><Link href={`/stock/${row.code}`} className="text-accent-blue">{row.name}<span className="block text-xs text-text-muted">{row.code}</span></Link></td>
          <td className={`p-2 font-number ${row.net_inflow >= 0 ? "text-stock-up" : "text-stock-down"}`}>{row.net_inflow > 0 ? "+" : ""}{(row.net_inflow / 10000).toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
          <td className="p-2 font-number">{row.price === null ? "—" : row.price.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
        </tr>)}</tbody>
      </table></div>
      <RankingPagination label="同花顺资金净流入" view={view} onPage={setPage} />
    </>}
    {!available && !pending && !failed && !paused && <p role="status" className="text-sm text-text-muted">该周期暂无可展示的资金榜，可刷新或展开东方财富榜。</p>}
  </>;
}
