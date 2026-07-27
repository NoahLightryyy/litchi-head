"use client";

import { useState } from "react";
import {
  BarChart3,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  Minus,
  Target,
  Activity,
  Trash2,
  CheckCircle2,
  XCircle,
  Clock,
  HelpCircle,
} from "lucide-react";
import {
  useRetroRecords,
  useRetroSummary,
  useUpdateAction,
  useUpdateOutcome,
  useRefreshRetro,
  useDeleteRecord,
} from "@/lib/hooks/use-retro";
import type { RetroRecord } from "@/lib/types/retro";

/** 复盘看板主组件 */
export function RetroBoard() {
  const [outcomeFilter, setOutcomeFilter] = useState<string>("");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const { data: records = [], isLoading: recordsLoading } = useRetroRecords({
    outcome: outcomeFilter || undefined,
    limit: 200,
  });
  const { data: summary, isLoading: summaryLoading } = useRetroSummary();
  const { mutate: updateAction, isPending: actionUpdating } = useUpdateAction();
  const { mutate: updateOutcome, isPending: outcomeUpdating } = useUpdateOutcome();
  const { mutate: refreshAll, isPending: refreshing } = useRefreshRetro();
  const { mutate: deleteRecord } = useDeleteRecord();

  const handleAction = (recordId: string, action: string) => {
    updateAction({ recordId, action });
  };

  const handleRefresh = () => {
    refreshAll();
  };

  return (
    <div className="space-y-6">
      {/* 聚合统计卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          icon={<BarChart3 className="w-4 h-4" />}
          label="总记录"
          value={summary?.total_records ?? "-"}
          loading={summaryLoading}
          color="blue"
        />
        <StatCard
          icon={<Target className="w-4 h-4" />}
          label="准确率"
          value={
            summary?.closed_records
              ? `${(summary.win_rate * 100).toFixed(0)}%`
              : "暂无数据"
          }
          sub={`${summary?.win_count ?? 0} 正确 / ${summary?.loss_count ?? 0} 错误`}
          loading={summaryLoading}
          color={summary && summary.win_rate >= 0.6 ? "green" : "gold"}
        />
        <StatCard
          icon={<Activity className="w-4 h-4" />}
          label="平均置信度"
          value={summary ? `${(summary.avg_confidence * 100).toFixed(0)}%` : "-"}
          loading={summaryLoading}
          color="purple"
        />
        <StatCard
          icon={<BarChart3 className="w-4 h-4" />}
          label="平均评分"
          value={summary ? summary.avg_score.toFixed(1) : "-"}
          sub={`今日 +${summary?.today_records ?? 0}`}
          loading={summaryLoading}
          color="blue"
        />
      </div>

      {/* 操作栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-text-muted">筛选:</span>
          {["", "pending", "correct", "wrong"].map((opt) => (
            <button
              key={opt}
              onClick={() => setOutcomeFilter(opt)}
              className={`px-3 py-1 rounded-md text-xs font-medium transition-colors ${
                outcomeFilter === opt
                  ? "bg-accent-blue text-white"
                  : "bg-bg-tertiary text-text-secondary hover:text-text-primary"
              }`}
            >
              {opt === "" ? "全部" : opt === "pending" ? "待判定" : opt === "correct" ? "正确" : "错误"}
            </button>
          ))}
        </div>
        <button
          onClick={handleRefresh}
          disabled={refreshing}
          className="flex items-center gap-2 px-4 py-2 rounded-md bg-accent-blue text-white text-sm font-medium hover:bg-accent-blue/90 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          {refreshing ? "刷新中..." : "更新涨跌幅"}
        </button>
      </div>

      {/* 记录列表 */}
      {recordsLoading ? (
        <div className="space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 rounded-md bg-bg-secondary animate-pulse border border-bg-tertiary" />
          ))}
        </div>
      ) : records.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-4">📋</div>
          <p className="text-sm text-text-muted">暂无复盘记录</p>
          <p className="text-xs text-text-muted mt-1">触发 AI 辩论后会自动生成记录</p>
        </div>
      ) : (
        <div className="border border-bg-tertiary rounded-md overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bg-secondary border-b border-bg-tertiary">
                <Th>时间</Th>
                <Th>股票</Th>
                <Th>共识</Th>
                <Th>置信度</Th>
                <Th>评分</Th>
                <Th>用户操作</Th>
                <Th>涨跌幅</Th>
                <Th>结果</Th>
                <Th className="text-right">操作</Th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <RetroRow
                  key={record.record_id}
                  record={record}
                  expanded={expandedId === record.record_id}
                  onToggle={() =>
                    setExpandedId(
                      expandedId === record.record_id ? null : record.record_id
                    )
                  }
                  onAction={handleAction}
                  onDelete={(id) => deleteRecord(id)}
                  actionUpdating={actionUpdating}
                />
              ))}
            </tbody>
          </table>
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
function RetroRow({
  record,
  expanded,
  onToggle,
  onAction,
  onDelete,
  actionUpdating,
}: {
  record: RetroRecord;
  expanded: boolean;
  onToggle: () => void;
  onAction: (id: string, action: string) => void;
  onDelete: (id: string) => void;
  actionUpdating: boolean;
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
          <span className="text-text-primary font-medium">{record.stock_code}</span>
          <span className="text-text-muted ml-1.5 text-xs">{record.stock_name}</span>
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
          <ActionChips
            recordId={record.record_id}
            current={record.user_action}
            disabled={actionUpdating}
            onChange={(action) => onAction(record.record_id, action)}
          />
        </td>
        <td className="px-4 py-3">
          {record.actual_return_pct !== null ? (
            <span
              className={`font-number ${
                record.actual_return_pct >= 0
                  ? "text-accent-green"
                  : "text-accent-red"
              }`}
            >
              {record.actual_return_pct >= 0 ? "+" : ""}
              {record.actual_return_pct.toFixed(2)}%
            </span>
          ) : (
            <span className="text-text-muted text-xs">待更新</span>
          )}
        </td>
        <td className="px-4 py-3">
          <OutcomeBadge outcome={record.outcome} />
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
        <h4 className="text-xs font-medium text-text-muted uppercase mb-2">用户操作 & 结果</h4>
        <div className="space-y-1.5">
          <DetailRow
            label="用户操作"
            value={
              record.user_action
                ? { buy: "买入", sell: "卖出", hold: "持有", skip: "跳过" }[
                    record.user_action
                  ] ?? record.user_action
                : "未记录"
            }
          />
          <DetailRow label="实际价格" value={record.actual_price ? `¥${record.actual_price.toFixed(2)}` : "未更新"} />
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

/* ── 用户操作按钮组 ── */
function ActionChips({
  recordId,
  current,
  disabled,
  onChange,
}: {
  recordId: string;
  current: string | null;
  disabled: boolean;
  onChange: (action: string) => void;
}) {
  const actions = [
    { key: "buy", label: "买入", color: "text-accent-green" },
    { key: "sell", label: "卖出", color: "text-accent-red" },
    { key: "hold", label: "持有", color: "text-accent-gold" },
    { key: "skip", label: "跳过", color: "text-text-muted" },
  ];
  return (
    <div className="flex gap-1">
      {actions.map((a) => (
        <button
          key={a.key}
          onClick={(e) => {
            e.stopPropagation();
            onChange(a.key);
          }}
          disabled={disabled}
          className={`px-2 py-0.5 rounded text-[10px] font-medium border transition-colors ${
            current === a.key
              ? `${a.color} border-current bg-current/10`
              : "text-text-muted border-transparent hover:border-bg-tertiary hover:text-text-secondary"
          } disabled:opacity-50`}
        >
          {a.label}
        </button>
      ))}
    </div>
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
