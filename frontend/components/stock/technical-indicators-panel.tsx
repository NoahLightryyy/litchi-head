"use client";

import { useTechnicalIndicators } from "@/lib/hooks/use-stock";
import type { TechnicalIndicators } from "@/lib/types/stock";

interface TechnicalIndicatorsPanelProps {
  code: string;
}

/** 技术指标面板：MA / RSI / MACD / 布林带 */
export function TechnicalIndicatorsPanel({ code }: TechnicalIndicatorsPanelProps) {
  const { data, isLoading, error } = useTechnicalIndicators(code);

  if (isLoading) {
    return (
      <div className="space-y-4 animate-pulse">
        <div className="grid grid-cols-2 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-28 rounded-lg bg-bg-tertiary" />
          ))}
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-8">
        <div className="text-3xl mb-3">📊</div>
        <p className="text-sm text-text-muted">暂无技术指标数据</p>
        <p className="text-xs text-text-muted mt-1">需要至少 60 个交易日数据</p>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* 四宫格指标摘要 */}
      <div className="grid grid-cols-2 gap-3">
        <MaCard ma={data.ma} />
        <RsiCard rsi={data.rsi} />
        <MacdCard macd={data.macd} />
        <BollingerCard bollinger={data.bollinger} price={null} />
      </div>

      {/* 详细说明 */}
      <div className="grid grid-cols-2 gap-4">
        <MaDetail ma={data.ma} />
        <MacdDetail macd={data.macd} />
      </div>
    </div>
  );
}

/* ── MA 卡片 ── */

function MaCard({ ma }: { ma: TechnicalIndicators["ma"] }) {
  const items = [
    { label: "MA5", value: ma.ma5 },
    { label: "MA10", value: ma.ma10 },
    { label: "MA20", value: ma.ma20 },
    { label: "MA60", value: ma.ma60 },
  ];

  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">移动平均线</h4>
      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {items.map((item) => (
          <div key={item.label} className="flex justify-between text-xs">
            <span className="text-text-muted">{item.label}</span>
            <span className="font-number text-text-primary font-medium">
              {item.value != null ? item.value.toFixed(2) : "--"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── RSI 卡片 ── */

function RsiCard({ rsi }: { rsi: number | null }) {
  const color =
    rsi == null
      ? "text-text-muted"
      : rsi >= 70
        ? "text-accent-red"
        : rsi <= 30
          ? "text-accent-green"
          : "text-accent-gold";

  const label =
    rsi == null
      ? "--"
      : rsi >= 70
        ? "超买"
        : rsi <= 30
          ? "超卖"
          : "中性";

  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">RSI (14)</h4>
      <div className="flex items-baseline gap-2">
        <span className={`text-2xl font-bold font-number ${color}`}>
          {rsi != null ? rsi.toFixed(1) : "--"}
        </span>
        <span className={`text-xs ${color}`}>{label}</span>
      </div>
      {/* RSI 刻度条 */}
      <div className="mt-2 h-1.5 rounded-full bg-bg-tertiary overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-300"
          style={{
            width: rsi != null ? `${Math.min(Math.max(rsi / 100 * 100, 0), 100)}%` : "0%",
            background:
              rsi == null
                ? "var(--color-bg-tertiary)"
                : rsi >= 70
                  ? "var(--color-accent-red)"
                  : rsi <= 30
                    ? "var(--color-accent-green)"
                    : "var(--color-accent-gold)",
          }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-text-muted mt-0.5">
        <span>0</span>
        <span>30</span>
        <span>70</span>
        <span>100</span>
      </div>
    </div>
  );
}

/* ── MACD 卡片 ── */

function MacdCard({ macd }: { macd: TechnicalIndicators["macd"] }) {
  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">MACD</h4>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">DIF</span>
          <span className="font-number text-text-primary font-medium">
            {macd.value != null ? macd.value.toFixed(4) : "--"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">DEA</span>
          <span className="font-number text-text-primary font-medium">
            {macd.signal != null ? macd.signal.toFixed(4) : "--"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">MACD 柱</span>
          <span className={`font-number font-medium ${
            macd.histogram != null
              ? macd.histogram >= 0
                ? "text-accent-red"
                : "text-accent-green"
              : "text-text-primary"
          }`}>
            {macd.histogram != null ? (macd.histogram >= 0 ? "+" : "") + macd.histogram.toFixed(4) : "--"}
          </span>
        </div>
      </div>
    </div>
  );
}

/* ── 布林带卡片 ── */

function BollingerCard({
  bollinger,
  price,
}: {
  bollinger: TechnicalIndicators["bollinger"];
  price: number | null;
}) {
  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">布林带</h4>
      <div className="space-y-1">
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">上轨</span>
          <span className="font-number text-accent-red font-medium">
            {bollinger.upper != null ? bollinger.upper.toFixed(2) : "--"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">中轨</span>
          <span className="font-number text-accent-gold font-medium">
            {bollinger.middle != null ? bollinger.middle.toFixed(2) : "--"}
          </span>
        </div>
        <div className="flex justify-between text-xs">
          <span className="text-text-muted">下轨</span>
          <span className="font-number text-accent-green font-medium">
            {bollinger.lower != null ? bollinger.lower.toFixed(2) : "--"}
          </span>
        </div>
        {bollinger.upper != null && bollinger.lower != null && bollinger.upper - bollinger.lower > 0 && (
          <div className="pt-1">
            <div className="h-1.5 rounded-full bg-bg-tertiary overflow-hidden relative">
              {/* 价格位置指示 */}
              <div className="absolute inset-y-0 left-0 bg-accent-blue/30 rounded-full transition-all" />
            </div>
            <div className="flex justify-between text-[10px] text-text-muted mt-0.5">
              <span className="font-number">{bollinger.lower.toFixed(0)}</span>
              <span className="font-number">{bollinger.middle?.toFixed(0)}</span>
              <span className="font-number">{bollinger.upper.toFixed(0)}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ── MA 详情 ── */

function MaDetail({ ma }: { ma: TechnicalIndicators["ma"] }) {
  const all = [
    { period: 5, value: ma.ma5 },
    { period: 10, value: ma.ma10 },
    { period: 20, value: ma.ma20 },
    { period: 60, value: ma.ma60 },
  ];

  // 判断排列状态
  const valid = all.filter((a) => a.value != null).map((a) => a.value!);
  let status = "数据不足";
  let statusColor = "text-text-muted";
  if (valid.length >= 3) {
    const sortedAsc = [...valid].sort((a, b) => a - b);
    const sortedDesc = [...valid].sort((a, b) => b - a);
    if (JSON.stringify(valid) === JSON.stringify(sortedAsc)) {
      status = "多头排列 📈";
      statusColor = "text-accent-green";
    } else if (JSON.stringify(valid) === JSON.stringify(sortedDesc)) {
      status = "空头排列 📉";
      statusColor = "text-accent-red";
    } else {
      status = "交叉整理 🔀";
      statusColor = "text-accent-gold";
    }
  }

  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">均线排列</h4>
      <div className={`text-sm font-medium ${statusColor}`}>{status}</div>
      {valid.length >= 2 && (
        <div className="mt-2 space-y-0.5">
          {all.map((a) => (
            <div key={a.period} className="flex justify-between text-xs">
              <span className="text-text-muted">MA{a.period}</span>
              <span className="font-number text-text-primary">{a.value != null ? a.value.toFixed(2) : "--"}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── MACD 详情 ── */

function MacdDetail({ macd }: { macd: TechnicalIndicators["macd"] }) {
  const signal =
    macd.value != null && macd.signal != null
      ? macd.value > macd.signal
        ? { text: "DIF 在 DEA 上方，偏多", color: "text-accent-red" }
        : { text: "DIF 在 DEA 下方，偏空", color: "text-accent-green" }
      : null;

  const histogramSignal =
    macd.histogram != null
      ? macd.histogram > 0
        ? { text: "柱线为正，动能增强", color: "text-accent-red" }
        : { text: "柱线为负，动能减弱", color: "text-accent-green" }
      : null;

  return (
    <div className="p-3 rounded-lg border border-bg-tertiary bg-bg-primary/50">
      <h4 className="text-xs font-medium text-text-muted mb-2 uppercase tracking-wider">MACD 研判</h4>
      {signal && (
        <div className={`text-xs ${signal.color} mb-1`}>{signal.text}</div>
      )}
      {histogramSignal && (
        <div className={`text-xs ${histogramSignal.color} mb-1`}>{histogramSignal.text}</div>
      )}
      {(macd.value == null || macd.signal == null) && (
        <div className="text-xs text-text-muted">数据不足以研判</div>
      )}
    </div>
  );
}
