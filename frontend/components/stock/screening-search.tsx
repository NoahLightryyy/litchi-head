"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { parseSectorDetailEnvelope, parseSectorsEnvelope } from "@/lib/market-contract";
import { addComparisonCompany, matchingBoards, readSearchCompanies } from "@/lib/screening";
import type { ComparisonCompany } from "@/lib/screening";
import type { SectorItem } from "@/lib/types/market";
import { MarketDataNotice } from "@/components/macro/market-data-notice";

interface SearchProps {
  selected: ComparisonCompany[];
  onAdd: (company: ComparisonCompany) => void;
}

const requestSignal = (signal: AbortSignal) => AbortSignal.any([signal, AbortSignal.timeout(20_000)]);
const buttonStyle = "rounded border border-bg-tertiary px-3 py-2 text-sm disabled:opacity-50";

function AddButton({ company, selected, onAdd }: SearchProps & { company: ComparisonCompany }) {
  const added = selected.some(item => item.code === company.code);
  return <button type="button" disabled={addComparisonCompany(selected, company) === selected}
    aria-label={`${added ? "已加入" : "加入对比"} ${company.name} ${company.code}`}
    onClick={() => onAdd(company)} className={`${buttonStyle} shrink-0 text-accent-blue`}>
    {added ? "已加入" : selected.length >= 4 ? "对比已满" : "加入对比"}
  </button>;
}

function CompanyRows({ companies, selected, onAdd }: SearchProps & { companies: ComparisonCompany[] }) {
  return <ul className="divide-y divide-bg-tertiary">
    {companies.map(company => <li key={company.code} className="flex flex-wrap items-center justify-between gap-2 py-3">
      <Link className="min-w-0 text-accent-blue" href={`/stock/${company.code}`}>
        {company.name} <span className="text-sm text-text-muted">{company.code}</span>
      </Link>
      <AddButton company={company} selected={selected} onAdd={onAdd} />
    </li>)}
  </ul>;
}

function BoardCompanies({ board, selected, onAdd }: SearchProps & { board: SectorItem }) {
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const members = useQuery({
    queryKey: ["screening", "members", "eastmoney", board.id],
    queryFn: async ({ signal }) => {
      const response = parseSectorDetailEnvelope(await api.getRaw(
        `/market/sector/${encodeURIComponent(board.id)}`, undefined, { signal: requestSignal(signal) }));
      return { ...response, companies: readSearchCompanies(response.data.stocks) };
    },
    retry: false, staleTime: 60_000,
  });
  const keyword = filter.trim().toLowerCase();
  const companies = members.data?.companies ?? [];
  const filtered = companies.filter(item => item.name.toLowerCase().includes(keyword) || item.code.includes(keyword));
  const pages = Math.max(1, Math.ceil(filtered.length / 20));
  const currentPage = Math.min(page, pages);
  return <section aria-label={`${board.name}成分股`} className="mt-4 rounded-lg border border-bg-tertiary p-4">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-semibold">{board.name} · 相关公司</h3>
      <Link href={`/sector/${board.id}`} className="text-sm text-accent-blue">查看板块详情 ↗</Link>
    </div>
    <p className="my-2 text-sm text-text-muted">关联依据：东方财富「{board.name}」板块成分股。归属该板块不代表主营业务占比或投资推荐。</p>
    <MarketDataNotice meta={members.data?.meta} refreshError={members.isError && !!members.data} />
    {members.fetchStatus === "paused" ? <p role="status">网络已断开，恢复连接后继续加载成分股。</p> :
      members.isPending ? <p role="status">正在加载成分股…</p> : null}
    {members.isError && <p role="alert">成分股加载失败。<button className="ml-2 text-accent-blue" onClick={() => void members.refetch()}>重试成分股</button></p>}
    {members.data && (companies.length ? <>
      <label className="mt-3 block text-sm">在板块内筛选公司
        <input value={filter} onChange={event => {setFilter(event.target.value); setPage(1);}}
          placeholder="名称或股票代码" className="mt-2 block w-full rounded border border-bg-tertiary bg-bg-primary p-2" />
      </label>
      <p className="mt-3 text-sm text-text-muted">返回 {companies.length} 家，筛选后 {filtered.length} 家</p>
      {filtered.length ? <CompanyRows companies={filtered.slice((currentPage - 1) * 20, currentPage * 20)} selected={selected} onAdd={onAdd} /> :
        <p className="py-4" role="status">该板块内没有匹配的公司，请调整筛选词。</p>}
      {pages > 1 && <nav aria-label="成分股分页" className="flex items-center gap-3">
        <button className={buttonStyle} disabled={currentPage === 1} onClick={() => setPage(currentPage - 1)}>上一页</button>
        <span className="text-sm">{currentPage} / {pages}</span>
        <button className={buttonStyle} disabled={currentPage === pages} onClick={() => setPage(currentPage + 1)}>下一页</button>
      </nav>}
    </> : <p role="status">该板块暂未返回可用成分股，请查看数据说明或重试。</p>)}
  </section>;
}

export function ScreeningSearch({ selected, onAdd }: SearchProps) {
  const [input, setInput] = useState("");
  const [query, setQuery] = useState("");
  const [validation, setValidation] = useState("");
  const [board, setBoard] = useState<SectorItem | null>(null);
  const [boardPage, setBoardPage] = useState(1);
  const stocks = useQuery({
    queryKey: ["screening", "search", query], enabled: !!query,
    queryFn: async ({ signal }) => readSearchCompanies(await api.get<unknown>(
      "/stocks/search", { q: query }, { signal: requestSignal(signal) })),
    retry: false, staleTime: 60_000,
  });
  const boards = useQuery({
    queryKey: ["screening", "boards", "eastmoney"], enabled: !!query,
    queryFn: async ({ signal }) => parseSectorsEnvelope(await api.getRaw(
      "/market/sectors", { source: "eastmoney", sort: "change_pct" }, { signal: requestSignal(signal) })),
    retry: false, staleTime: 60_000,
  });
  const matches = matchingBoards(boards.data?.data ?? [], query);
  const boardPages = Math.max(1, Math.ceil(matches.length / 8));
  const currentBoardPage = Math.min(boardPage, boardPages);
  function search(event: React.FormEvent) {
    event.preventDefault();
    const next = input.trim();
    if (!next) {setValidation("请输入股票代码、公司名称、行业或概念。"); return;}
    setValidation(""); setBoard(null); setBoardPage(1);
    if (next === query) {void stocks.refetch(); void boards.refetch();}
    setQuery(next);
  }
  return <section aria-label="搜索公司与板块" className="rounded-lg border border-bg-tertiary bg-bg-secondary p-4">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-lg font-semibold">1. 搜索公司或板块</h2>
      {selected.length > 0 && <a href="#screening-comparison" className="text-sm text-accent-blue">查看对比（{selected.length} / 4）↓</a>}
    </div>
    <form onSubmit={search} className="flex gap-2">
      <input aria-label="搜索股票、行业或概念" value={input} onChange={event => setInput(event.target.value)}
        placeholder="股票代码、名称、行业或概念，如半导体" className="min-w-0 flex-1 rounded border border-bg-tertiary bg-bg-primary p-3" />
      <button type="submit" className="shrink-0 rounded bg-accent-blue px-4 text-white">搜索</button>
    </form>
    {validation && <p role="alert" className="mt-2">{validation}</p>}
    {!query && <p className="mt-3 text-sm text-text-muted">先搜索，再从结果中选择公司加入对比；搜索行业或概念后，可展开板块查看相关公司。</p>}
    {query && <div className="mt-4 space-y-4">
      <p className="text-sm text-text-muted" role="status">“{query}”的搜索结果</p>
      <section aria-label="匹配公司">
        <h3 className="font-semibold">匹配公司</h3>
        {stocks.fetchStatus === "paused" ? <p role="status">网络已断开，恢复连接后继续搜索公司。</p> :
          stocks.isFetching ? <p role="status">正在搜索公司…</p> : null}
        {stocks.isError && <p role="alert">公司搜索失败。<button className="ml-2 text-accent-blue" onClick={() => void stocks.refetch()}>重试公司搜索</button></p>}
        {stocks.data && <CompanyRows companies={stocks.data} selected={selected} onAdd={onAdd} />}
        {stocks.isSuccess && !stocks.data.length && <p className="py-2 text-sm text-text-muted">没有名称或代码匹配的公司，可继续查看下方相关板块。</p>}
        {!!stocks.data && stocks.data.length >= 20 && <p className="text-sm text-text-muted">公司接口最多返回 20 项；请输入更完整的名称或代码缩小范围。</p>}
      </section>
      <section aria-label="相关板块">
        <h3 className="font-semibold">相关行业与概念{boards.data ? ` · ${matches.length}` : ""}</h3>
        <MarketDataNotice meta={boards.data?.meta} refreshError={boards.isError && !!boards.data} />
        {boards.fetchStatus === "paused" ? <p role="status">网络已断开，恢复连接后继续搜索板块。</p> :
          boards.isFetching ? <p role="status">正在搜索板块…</p> : null}
        {boards.isError && <p role="alert">板块搜索失败。<button className="ml-2 text-accent-blue" onClick={() => void boards.refetch()}>重试板块搜索</button></p>}
        {boards.data && !matches.length && <p className="py-2 text-sm text-text-muted">当前返回的板块中没有匹配项，请尝试其他行业或概念名称。</p>}
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          {matches.slice((currentBoardPage - 1) * 8, currentBoardPage * 8).map(item =>
            <button key={item.id} type="button" aria-pressed={board?.id === item.id} onClick={() => setBoard(item)}
              className={`rounded border p-3 text-left ${board?.id === item.id ? "border-accent-blue bg-bg-tertiary" : "border-bg-tertiary"}`}>
              <span className="font-medium">{item.name}</span>
              <span className="block text-xs text-text-muted">{item.category === "industry" ? "行业" : "概念"} · 东方财富 · {item.id}</span>
              <span className="mt-1 block text-sm text-accent-blue">查看相关公司</span>
            </button>)}
        </div>
        {boardPages > 1 && <nav aria-label="板块分页" className="mt-3 flex items-center gap-3">
          <button className={buttonStyle} disabled={currentBoardPage === 1} onClick={() => setBoardPage(currentBoardPage - 1)}>上一组板块</button>
          <span>{currentBoardPage} / {boardPages}</span>
          <button className={buttonStyle} disabled={currentBoardPage === boardPages} onClick={() => setBoardPage(currentBoardPage + 1)}>下一组板块</button>
        </nav>}
        {board && <BoardCompanies key={board.id} board={board} selected={selected} onAdd={onAdd} />}
      </section>
    </div>}
  </section>;
}
