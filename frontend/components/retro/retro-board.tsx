"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { readRetroObservations, observationLabel, type RetroObservation } from "@/lib/retro-observations";
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Minus,
  Trash2,
  CheckCircle2,
  XCircle,
  Clock,
} from "lucide-react";
import {
  useRetroRecords,
  useRetroSummary,
  useDeleteRecord,
} from "@/lib/hooks/use-retro";
import type { RetroRecord } from "@/lib/types/retro";

/** 复盘看板主组件 */
export function RetroBoard() {
  const [page, setPage] = useState(1);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: records = [], isLoading: recordsLoading, isError: recordsFailed, refetch: retryRecords } = useRetroRecords({
    limit: 200,
  });
  const { data: summary, isLoading: summaryLoading, isError: summaryFailed, refetch: retrySummary } = useRetroSummary();
  const { mutate: deleteRecord, isError: deleteFailed } = useDeleteRecord();

  const pageCount = Math.max(1, Math.ceil(records.length / 10));
  const currentPage = Math.min(page, pageCount);
  const visible = records.slice((currentPage - 1) * 10, currentPage * 10);
  const observations = useQuery({
    queryKey: ["retro", "observations", visible.map(r => r.record_id)],
    queryFn: ({ signal }) => readRetroObservations(visible, AbortSignal.any([signal, AbortSignal.timeout(60_000)])),
    enabled: visible.length > 0,
    staleTime: 30_000, refetchInterval: 60_000, retry: false,
  });
  const byId = new Map(observations.data?.map(item => [item.record_id, item]));
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">研究记录</h1>
        <p className="mt-2 text-sm text-text-muted">打开本页会自动查看研究后的收盘价变化，每分钟检查更新，不用你填写结果。以记录日期起首个可取得收盘价为起点；这段变化不是账户盈亏，也不是研究的最终成绩。</p>
        <p className="mt-1 text-xs text-text-muted">历史评分和置信度保留原始值；当前接口未提供样本有效性和校准证明，暂不以其均值评价研究质量。</p>
      </div>
      {summaryFailed && <div role="alert" className="text-sm text-accent-red">研究统计加载失败。<button className="ml-2 underline" onClick={() => void retrySummary()}>重试统计</button></div>}
      {deleteFailed && <p role="alert" className="text-sm text-accent-red">记录更新未成功确认，请重新加载记录核对后再操作。</p>}
      {/* 聚合统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<BarChart3 className="w-4 h-4" />}
          label="研究记录数"
          value={summaryFailed ? "加载失败" : summary?.total_records ?? "-"}
          loading={summaryLoading}
          color="blue"
        />
        <StatCard
          icon={<CheckCircle2 className="w-4 h-4" />}
          label="本页已更新行情"
          value={observations.data?.filter(item => item.status === "observed").length ?? "-"}
          loading={summaryLoading}
          color="green"
        />
        <StatCard
          icon={<Clock className="w-4 h-4" />}
          label="本页等后续收盘"
          value={observations.data?.filter(item => item.status === "waiting").length ?? "-"}
          loading={summaryLoading}
          color="purple"
        />
        <StatCard
          icon={<BarChart3 className="w-4 h-4" />}
          label="今日新增记录"
          value={summaryFailed ? "加载失败" : summary?.today_records ?? "-"}
          loading={summaryLoading}
          color="blue"
        />
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-text-muted">
        <p>每页10条 · 使用已取得的历史日线，通常次日补齐；不复权，分红和除权可能影响比较。</p>
        <button disabled={observations.isFetching || !visible.length} onClick={() => void observations.refetch()} className="text-accent-blue disabled:opacity-50">{observations.isFetching ? "正在更新行情…" : "更新市场观察"}</button>
      </div>
      {observations.isError && <p role="alert" className="text-sm text-accent-gold">这次行情没有更新成功；已显示的价格仍对应原来的收盘日期。可以稍后刷新。</p>}

      {/* 记录列表 */}
      {recordsLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-md bg-bg-secondary animate-pulse border border-bg-tertiary" />
          ))}
        </div>
      ) : recordsFailed ? (
        <div role="alert" className="rounded border border-accent-red/30 p-6 text-sm">
          研究记录加载失败，无法确认是否有记录。
          <button className="ml-3 text-accent-blue underline" onClick={() => void retryRecords()}>重新加载记录</button>
        </div>
      ) : records.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">📋</div>
          <p className="text-sm text-text-muted">暂无复盘记录</p>
          <p className="text-xs text-text-muted mt-1">触发 AI 辩论后会自动生成记录</p>
        </div>
      ) : (
        <div className="border border-bg-tertiary rounded-md overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bg-secondary border-b border-bg-tertiary">
                <Th>时间</Th>
                <Th>股票</Th>
                <Th>共识</Th>
                <Th>原始置信度</Th>
                <Th>原始评分</Th>
                <Th>操作标签</Th>
                <Th>收盘价变化</Th>
                <Th>当前观察</Th>
                <Th className="text-right">操作</Th>
              </tr>
            </thead>
            <tbody>
              {visible.map((record) => (
                <RetroRow
                  key={record.record_id}
                  record={record}
                  observation={byId.get(record.record_id)}
                  observationFailed={observations.isError}
                  expanded={expandedId === record.record_id}
                  onToggle={() =>
                    setExpandedId(
                      expandedId === record.record_id ? null : record.record_id
                    )
                  }
                  onDelete={(id) => deleteRecord(id)}
                />
              ))}
            </tbody>
          </table>
          <nav aria-label="研究记录分页" className="flex items-center justify-end gap-4 p-4 text-sm">
            <span>第 {currentPage} / {pageCount} 页 · 已加载 {records.length} 条</span>
            <button disabled={currentPage <= 1} className="disabled:opacity-40" onClick={() => setPage(currentPage - 1)}>上一页</button>
            <button disabled={currentPage >= pageCount} className="disabled:opacity-40" onClick={() => setPage(currentPage + 1)}>下一页</button>
          </nav>
        </div>
      )}
    </div>
  );
}

/* ── 表头 ── */
function Th({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`px-4 py-3 text-left text-xs font-medium text-text-muted uppercase tracking-wider ${className}`}
    >
      {children}
    </th>
  );
}

/* ── 单行记录 ── */
export function RetroRow({
  record,
  observation,
  observationFailed = false,
  expanded,
  onToggle,
  onDelete,
}: {
  record: RetroRecord;
  observation?: RetroObservation;
  observationFailed?: boolean;
  expanded: boolean;
  onToggle: () => void;
  onDelete: (id: string) => void;
}) {
  const timeStr = record.created_at
    ? new Date(record.created_at).toLocaleString("zh-CN", {
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      })
    : "-";

  return (
    <>
      <tr
        className="border-b border-bg-tertiary hover:bg-bg-secondary/50 cursor-pointer transition-colors"
        onClick={onToggle}
      >
        <td className="px-4 py-3 text-text-muted font-number text-xs">{timeStr}</td>
        <td className="px-4 py-3">
          <Link href={`/stock/${record.stock_code}`} onClick={e => e.stopPropagation()} className="text-accent-blue hover:underline block min-w-24">
            <span className="block font-medium">{record.stock_code}</span>
            <span className="text-xs">{record.stock_name}</span>
          </Link>
        </td>
        <td className="px-4 py-3">
          <ConsensusBadge consensus={record.consensus} />
        </td>
        <td className="px-4 py-3">
          <span className="font-number text-text-primary">
            {(record.confidence * 100).toFixed(0)}%
          </span>
        </td>
        <td className="px-4 py-3">
          <span className="font-number text-text-secondary">
            {record.weighted_score.toFixed(1)}
          </span>
        </td>
        <td className="px-4 py-3">
          {record.user_action ? ({buy:"买入",sell:"卖出",hold:"持有",skip:"跳过"}[record.user_action] ?? record.user_action) : "未记录"}
        </td>
        <td className="px-4 py-3">
          {observation?.status === "observed" && observation.change_pct != null ? <>
            <span className={`font-number ${observation.change_pct >= 0 ? "text-accent-green" : "text-accent-red"}`}>{observation.change_pct >= 0 ? "+" : ""}{observation.change_pct.toFixed(2)}%</span>
            <span className="block text-xs text-text-muted whitespace-nowrap">{observation.baseline_date} →<br />{observation.latest_date}</span>
          </> : <span className="text-text-muted text-xs">{observation?.status === "waiting" ? "等后续收盘" : observation || observationFailed ? "暂无行情" : "正在查看…"}</span>}
        </td>
        <td className="px-4 py-3 min-w-36 text-xs">
          {observation?.alignment ? <>{observationLabel[observation.alignment]}<span className="block text-text-muted mt-1">{observation.message}</span></> : observation?.message ?? (observationFailed ? "暂未取得行情" : "正在读取市场观察")}
        </td>
        <td className="px-4 py-3 text-right">
          <button
            onClick={(e) => {
              e.stopPropagation();
              onDelete(record.record_id);
            }}
            className="p-1 rounded hover:bg-bg-tertiary text-text-muted hover:text-accent-red transition-colors"
            title="删除"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </td>
      </tr>
      {expanded && (
        <tr>
          <td colSpan={9} className="px-6 py-4 bg-bg-secondary/30">
            {observation && <div className="mb-4 text-sm text-text-muted">
              <p>{observation.message}</p>
              {observation.baseline_price != null && <p>起点收盘 {observation.baseline_date}：¥{observation.baseline_price}；最新收盘 {observation.latest_date}：¥{observation.latest_price} · 腾讯 · 不复权</p>}
            </div>}
            <DetailPanel record={record} />
          </td>
        </tr>
      )}
    </>
  );
}

/* ── 展开详情 ── */
function DetailPanel({ record }: { record: RetroRecord }) {
  const dir = record.direction_distribution || {};
  return (
    <div className="grid grid-cols-2 gap-6 text-sm">
      <div>
        <h4 className="text-xs font-medium text-text-muted uppercase mb-2">辩论信息</h4>
        <div className="space-y-1.5">
          <DetailRow label="会话 ID" value={record.session_id.slice(-12)} />
          <DetailRow label="耗时" value={`${(record.debate_latency_ms / 1000).toFixed(1)}s`} />
          <DetailRow label="辩论时价格" value={record.price_at_debate ? `¥${record.price_at_debate.toFixed(2)}` : "无"} />
          <DetailRow label="方向分布" value={`看涨 ${dir.Bullish ?? 0} / 看跌 ${dir.Bearish ?? 0} / 中性 ${dir.Neutral ?? 0}`} />
          <DetailRow label="平均评分" value={record.avg_score.toFixed(1)} />
        </div>
      </div>
      <div>
        <h4 className="text-xs font-medium text-text-muted uppercase mb-2">操作标签与市场观察</h4>
        <div className="space-y-1.5">
          <DetailRow
            label="操作标签"
            value={
              record.user_action
                ? { buy: "买入", sell: "卖出", hold: "持有", skip: "跳过" }[
                    record.user_action
                  ] ?? record.user_action
                : "未记录"
            }
          />
          <DetailRow label="旧观察价格" value={record.actual_price ? `¥${record.actual_price.toFixed(2)}` : "未更新"} />
          <div>历史人工标记：<OutcomeBadge outcome={record.outcome} /></div>
          <DetailRow label="评级分布" value={formatRatingDist(record.rating_distribution)} />
        </div>
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-text-muted">{label}</span>
      <span className="text-text-primary">{value}</span>
    </div>
  );
}

/* ── 方向徽章 ── */
function ConsensusBadge({ consensus }: { consensus: string }) {
  const isBullish = consensus.includes("看涨") || consensus === "Bullish";
  const isBearish = consensus.includes("看跌") || consensus === "Bearish";
  const Icon = isBullish ? TrendingUp : isBearish ? TrendingDown : Minus;
  const color = isBullish
    ? "text-accent-green bg-accent-green/10"
    : isBearish
      ? "text-accent-red bg-accent-red/10"
      : "text-accent-gold bg-accent-gold/10";
  return (
    <span
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${color}`}
    >
      <Icon className="w-3 h-3" />
      {isBullish ? "看涨" : isBearish ? "看跌" : "中性"}
    </span>
  );
}

/* ── 结果徽章 ── */
function OutcomeBadge({ outcome }: { outcome: string }) {
  if (outcome === "correct")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-accent-green bg-accent-green/10">
        <CheckCircle2 className="w-3 h-3" /> 正确
      </span>
    );
  if (outcome === "wrong")
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-accent-red bg-accent-red/10">
        <XCircle className="w-3 h-3" /> 错误
      </span>
    );
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium text-text-muted bg-bg-tertiary">
      <Clock className="w-3 h-3" /> 待判定
    </span>
  );
}

/* ── 统计卡片 ── */
function StatCard({
  icon,
  label,
  value,
  sub,
  loading,
  color,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  loading: boolean;
  color: "blue" | "green" | "gold" | "purple" | "red";
}) {
  const colorMap = {
    blue: "bg-accent-blue/10 text-accent-blue",
    green: "bg-accent-green/10 text-accent-green",
    gold: "bg-accent-gold/10 text-accent-gold",
    purple: "bg-accent-purple/10 text-accent-purple",
    red: "bg-accent-red/10 text-accent-red",
  };

  return (
    <div className="p-4 rounded-md border border-bg-tertiary bg-bg-secondary">
      <div className="flex items-center gap-2 mb-2">
        <span className={colorMap[color]}>{icon}</span>
        <span className="text-xs text-text-muted">{label}</span>
      </div>
      {loading ? (
        <div className="h-6 w-20 bg-bg-tertiary rounded animate-pulse" />
      ) : (
        <>
          <div className="text-xl font-bold font-number text-text-primary">
            {value}
          </div>
          {sub && <div className="text-xs text-text-muted mt-0.5">{sub}</div>}
        </>
      )}
    </div>
  );
}

/* ── 工具函数 ── */
function formatRatingDist(dist: Record<string, number>): string {
  const entries = Object.entries(dist);
  if (entries.length === 0) return "无数据";
  return entries.map(([k, v]) => `${k}: ${v}`).join(" | ");
}
