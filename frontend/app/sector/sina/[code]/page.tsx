"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { fetchSinaMembers, fetchSinaSectors } from "@/lib/api/market";
import { compareSinaSector } from "@/lib/sector-navigation";
import { MarketDataNotice } from "@/components/macro/market-data-notice";
import { SectorFundamentals } from "@/components/sector/sector-fundamentals";

const signed = (value: number) => `${value > 0 ? "+" : ""}${value.toFixed(2)}`;
const color = (value: number) => value > 0 ? "text-accent-green" : value < 0 ? "text-accent-red" : "text-text-muted";
const date = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
const button = "rounded-md border border-bg-tertiary px-3 py-2 text-sm text-accent-blue disabled:opacity-40 hover:bg-bg-tertiary";

export default function SinaSectorPage() {
  const { code } = useParams<{ code: string }>();
  return <SinaSector key={code} code={code} />;
}

function SinaSector({ code }: { code: string }) {
  const [page, setPage] = useState(1);
  const valid = /^(new_|gn_)[A-Za-z0-9_]+$/.test(code);
  const boards = useQuery({ queryKey: ["market", "sina", "sectors"],
    queryFn: ({ signal }) => fetchSinaSectors(AbortSignal.any([signal, AbortSignal.timeout(12_000)])),
    retry: false, staleTime: 30_000, enabled: valid });
  const sector = boards.data?.data.find(s => s.id === `sina:${code}`);
  const members = useQuery({ queryKey: ["market", "sina", code, "members", page],
    queryFn: ({ signal }) => fetchSinaMembers(code, page, AbortSignal.any([signal, AbortSignal.timeout(12_000)])),
    retry: false, staleTime: 30_000, enabled: !!sector });
  const comparison = sector && boards.data ? compareSinaSector(sector, boards.data.data) : null;
  const data = members.data?.data;
  const pages = Math.max(1, Math.ceil((data?.total ?? 0) / 20));
  return <div className="max-w-7xl mx-auto flex flex-col gap-6">
    <nav className="flex items-center gap-2 text-sm text-text-muted">
      <Link href="/" className="text-accent-blue hover:underline">市场总览</Link><span>/</span>
      <Link href="/industries" className="text-accent-blue hover:underline">行业研究</Link><span>/</span>
      <span>{sector?.name ?? "新浪板块"}</span>
    </nav>
    {boards.isLoading && <p role="status" className="p-8 bg-bg-secondary rounded-lg">正在加载板块概览…</p>}
    {boards.isError && !sector && <div role="alert" className="p-6 bg-bg-secondary rounded-lg">
      <p className="mb-3">板块概览暂时加载失败，请检查网络后重试。</p>
      <button className={button} disabled={boards.isFetching} onClick={() => void boards.refetch()}>重新加载板块</button>
    </div>}
    {(!valid || (boards.data && !sector)) && <p role="status">当前新浪榜单中没有这个板块。<Link href="/industries" className="text-accent-blue">返回行业研究</Link></p>}
    {sector && comparison && <>
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div><p className="text-xs text-text-muted mb-2">板块研究 · 新浪{sector.category === "industry" ? "行业" : "概念"}</p>
          <h1 className="text-2xl font-semibold">{sector.name}</h1></div>
        <div className="flex flex-wrap items-center gap-3">
          <button className={button} disabled={boards.isFetching || members.isFetching} onClick={() => { void boards.refetch(); void members.refetch(); }}>刷新数据</button>
          <a className="text-xs text-text-muted hover:underline" target="_blank" rel="noopener noreferrer"
            href={`https://money.finance.sina.com.cn/moneyflow/#!bk!${sector.category === "industry" ? 0 : 1}/${code}`}>查看原始数据（新浪）↗</a>
        </div>
      </header>
      <section aria-label="板块行情概览" className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        {[
          { title: "板块涨跌幅", value: `${signed(sector.change_pct)}%`, tone: color(sector.change_pct) },
          { title: "新浪净流入（亿）", value: sector.net_flow == null ? "—" : signed(sector.net_flow), tone: color(sector.net_flow ?? 0) },
          { title: "同类涨幅排名", value: `${comparison.changeRank} / ${comparison.total}`, tone: "" },
          { title: "同类净流入排名", value: `${comparison.flowRank ?? "—"} / ${comparison.total}`, tone: "" },
        ].map(item => <div key={item.title} className="p-5 rounded-lg bg-bg-secondary border border-bg-tertiary">
          <p className="text-xs text-text-muted mb-3">{item.title}</p><p className={`text-xl font-number ${item.tone}`}>{item.value}</p>
        </div>)}
      </section>
      <section className="p-5 rounded-lg bg-bg-secondary border border-bg-tertiary">
        <h2 className="font-semibold mb-3">板块观察 <span className="text-xs text-text-muted font-normal ml-2">本站按行情计算</span></h2>
        <p className="text-sm leading-7 text-text-secondary">{sector.name}在当前新浪{sector.category === "industry" ? "行业" : "概念"}分类的 {comparison.total} 个板块中，涨幅并列排名口径为第 {comparison.changeRank}；资金净流入排名为第 {comparison.flowRank ?? "—"}。
          涨跌幅反映价格变化，净流入反映来源口径下的资金差额，两项分开观察，不合成为买卖评级。</p>
        <p className="text-xs text-text-muted mt-3">比较范围仅包含同一来源、同一分类的板块，同值并列。<a href="#fundamentals" className="text-accent-blue underline">查看成分股基本面研究</a></p>
      </section>
      <SectorFundamentals members={data?.stocks ?? []} />
      <details className="text-xs text-text-muted rounded-lg border border-bg-tertiary p-4">
        <summary className="cursor-pointer">数据口径与更新时间{sector.service_updated_at ? ` · ${date(sector.service_updated_at)}（北京时间）` : ""}</summary>
        <div className="mt-3"><MarketDataNotice meta={boards.data?.meta} refreshError={boards.isError} />
          <p className="mt-2">服务更新时间不是逐条行情时间。板块和成分股分别加载，不将成分股页内合计作为整个板块的统计。</p></div>
      </details>
      <section className="rounded-lg border border-bg-tertiary bg-bg-secondary overflow-hidden">
        <div className="p-5 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">板块成分股</h2><span className="text-xs text-text-muted">按新浪净流入排序 · 点击股票进入站内分析</span>
        </div>
        {members.isLoading && <p role="status" className="p-6">正在加载成分股…</p>}
        {members.isError && <div role="alert" className="p-5 text-sm text-accent-red">
          <p>成分股暂时加载失败，板块概览仍可查看。{data && "以下保留上次成功的数据。"}</p>
          <button className={`${button} mt-3`} disabled={members.isFetching} onClick={() => void members.refetch()}>重新加载成分股</button>
        </div>}
        {data && <>
          <p className="px-5 pb-3 text-xs text-text-muted">共 {data.total} 只 · 本页 {data.stocks.length} 只 · 资金服务更新 {date(data.service_updated_at)}（北京时间）</p>
          {data.stocks.length === 0 ? <p role="status" className="p-5">当前页未返回成分股，请返回首页或刷新。</p> :
            <div className="overflow-x-auto"><table className="w-full text-sm whitespace-nowrap">
              <thead className="text-xs text-text-muted bg-bg-primary"><tr>{["股票", "价格（元）", "涨跌幅", "新浪净流入（亿）"].map((title, i) => <th key={title} className={`px-5 py-3 font-normal ${i ? "text-right" : "text-left"}`}>{title}</th>)}</tr></thead>
              <tbody>{data.stocks.map(stock => <tr key={stock.code} className="border-t border-bg-tertiary hover:bg-bg-primary">
                <td className="px-5 py-3"><Link className="text-accent-blue hover:underline" href={`/stock/${stock.code}`}>{stock.name}</Link><span className="block text-xs text-text-muted mt-1">{stock.code}</span></td>
                <td className="px-5 py-3 text-right font-number">{stock.price.toFixed(2)}</td>
                <td className={`px-5 py-3 text-right font-number ${color(stock.change_pct)}`}>{signed(stock.change_pct)}%</td>
                <td className={`px-5 py-3 text-right font-number ${color(stock.net_flow)}`}>{signed(stock.net_flow)}</td>
              </tr>)}</tbody>
            </table></div>}
          <nav aria-label="成分股分页" className="p-4 flex flex-wrap justify-center items-center gap-3 border-t border-bg-tertiary">
            <button className={button} disabled={page === 1} onClick={() => setPage(1)}>首页</button>
            <button className={button} disabled={page === 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span className="text-sm">第 {page} / {pages} 页</span>
            <button className={button} disabled={page >= pages} onClick={() => setPage(page + 1)}>下一页</button>
            <button className={button} disabled={page >= pages} onClick={() => setPage(pages)}>尾页</button>
          </nav>
        </>}
        {members.isError && !data && page > 1 && <button className={`${button} m-4`} onClick={() => setPage(1)}>返回成分股首页</button>}
      </section>
    </>}
  </div>;
}
