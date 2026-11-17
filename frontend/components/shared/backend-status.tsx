"use client";

import { useLocale } from "./locale-provider";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  type BackendState,
  type DiagnoseResult,
  classifyBackendProbe,
  normalizeDataSourceDiagnostics,
  partitionDiagnostics,
  backendStateLabel,
} from "@/lib/backend-health";

/* ── 后端连接状态 ── */
const POLL_INTERVAL = 15_000;
const INITIAL_RETRIES = 5;   // up to ~10s of initial retries
const RETRY_DELAY = 2_000;
// 使用相对路径走 Next.js rewrites 代理 → 后端，避免 CORS 问题
const BASE_URL = "";

interface BackendProbe {
  state: Exclude<BackendState, "checking">;
  diagnose: DiagnoseResult | null;
  message: string | null;
}

async function probeBackend(): Promise<BackendProbe> {
  const healthRes = await fetch(`${BASE_URL}/api/health`, {
    signal: AbortSignal.timeout(3000),
  });
  if (!healthRes.ok) {
    throw new Error("health check failed");
  }

  try {
    const diagnoseRes = await fetch(`${BASE_URL}/api/health/data-source`, {
      signal: AbortSignal.timeout(5000),
    });
    if (!diagnoseRes.ok) {
      throw new Error("diagnose failed");
    }

    const diagnose = normalizeDataSourceDiagnostics(await diagnoseRes.json());
    if (diagnose === null) {
      throw new Error("diagnose contract mismatch");
    }
    const classification = classifyBackendProbe(true, diagnose.status);
    return { ...classification, diagnose };
  } catch {
    const classification = classifyBackendProbe(true, null);
    return { ...classification, diagnose: null };
  }
}

const CHECK_LABELS: Record<string, string> = {
  all_stocks: "股票搜索目录",
  dns_fallback: "备用域名解析",
  "kline:daily": "日 K 线",
  "kline:weekly": "周 K 线",
  "kline:monthly": "月 K 线",
  valuation: "估值数据",
  quotes: "实时行情",
  news: "新闻资讯",
  "market_index:eastmoney": "指数 · 东方财富",
  "market_index:sina": "指数 · 新浪",
  "market_index:tencent": "指数 · 腾讯",
};

/** Global source diagnostics are secondary to the data shown by each page. */
export function BackendDiagnosticsNotice({
  degraded,
  diagnose,
  message,
  t,
}: {
  degraded: boolean;
  diagnose: DiagnoseResult | null;
  message: string | null;
  t: (text: string) => string;
}) {
  if (!degraded && diagnose?.status !== "healthy_with_warnings") return null;
  const checks = Object.entries(diagnose?.checks ?? {});
  const { issues, backupFailures } = partitionDiagnostics(diagnose?.checks ?? {});
  const issueCount = issues.length;
  const summary = message
    ? t("数据诊断暂不可用")
    : degraded
      ? `${t("数据诊断")} · ${issueCount > 0 ? `${issueCount} ${t("项异常")}` : t("部分异常")}`
      : t("数据诊断 · 备用来源暂不可用");

  return (
    <details className="px-4 py-2 text-xs text-text-muted border-b border-bg-tertiary">
      <summary className="cursor-pointer">
        <span aria-hidden="true" className="inline-block w-1.5 h-1.5 rounded-full bg-amber-500 mx-1.5" />
        {summary}
        {!message && issues.some(([name]) => name === "all_stocks") && ` · ${t(
          diagnose?.checks.all_stocks?.errorCode === "STOCK_CATALOG_PARTIAL" ? "股票名称搜索可能不完整" : "股票名称搜索暂不可用")}`}
        {!message && backupFailures.length > 0 && ` · ${t("指数已使用备用来源")}`}
      </summary>
      <div className="mt-2 space-y-2">
        <p>{t("以下为已访问数据服务的诊断；各页面的数据可用性以对应内容提示为准。")}</p>
        {message && <p>{t(message)}</p>}
        {checks.length > 0 && (
          <ul className="space-y-1">
            {checks.map(([name, check]) => {
              const label = CHECK_LABELS[name];
              const status = check.status === "pass" ? "可用" : check.status === "warn" ? "暂无数据" : "请求失败";
              const details = [...new Set([check.message, check.error].filter(Boolean))];
              return (
                <li key={name}>
                  {label ? `${t(label)} (${name})` : name}：{t(status)}
                  {details.length > 0 && ` · ${details.join("；")}`}
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </details>
  );
}

/* ── 后端状态横幅（页面顶部） ── */
export function BackendStatusIndicator() {
  const { t } = useLocale();
  const [state, setState] = useState<BackendState>("checking");
  const [diagnose, setDiagnose] = useState<DiagnoseResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const check = useCallback(async () => {
    for (let i = 0; i < INITIAL_RETRIES; i++) {
      try {
        const result = await probeBackend();
        if (!mountedRef.current) return;
        setDiagnose(result.diagnose);
        setMessage(result.message);
        setState(result.state);
        return; // success
      } catch {
        if (!mountedRef.current) return;
        // Last attempt — set disconnected
        if (i >= INITIAL_RETRIES - 1) {
          setState("disconnected");
          return;
        }
        // Wait before retry
        await new Promise((r) => setTimeout(r, RETRY_DELAY));
      }
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    const initialCheck = setTimeout(() => void check(), 0);
    const interval = setInterval(check, POLL_INTERVAL);
    return () => {
      mountedRef.current = false;
      clearTimeout(initialCheck);
      clearInterval(interval);
    };
  }, [check]);

  /* ── checking 状态（刚启动还在试）—— 灰色提示 ── */
  if (state === "checking") {
    return (
      <div className="px-4 py-2 bg-gray-500/10 text-text-muted text-xs text-center border-b border-bg-tertiary flex items-center justify-center gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-400 animate-pulse" />
        <span>{t("正在连接后端服务...")}</span>
      </div>
    );
  }

  /* ── 断开状态 —— 红色横幅 ── */
  if (state === "disconnected") {
    return (
      <div className="px-4 py-2 bg-accent-red/10 text-accent-red text-xs text-center border-b border-accent-red/20 flex items-center justify-center gap-2">
        <span className="inline-block w-1.5 h-1.5 rounded-full bg-accent-red animate-pulse" />
        <span>{t("后端服务未连接 — 请启动后端服务（port 8000）")}</span>
        <button
          onClick={check}
          className="underline hover:no-underline text-accent-red/80"
        >
          {t("重试")}
        </button>
      </div>
    );
  }

  return <BackendDiagnosticsNotice degraded={state === "degraded"} diagnose={diagnose} message={message} t={t} />;
}

/* ── 顶部栏右侧连接状态小点 ── */
export function HeaderStatusDot() {
  const { t } = useLocale();
  const [state, setState] = useState<BackendState>("checking");
  const [message, setMessage] = useState<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    let cancelled = false;

    const check = async (): Promise<void> => {
      for (let i = 0; i < INITIAL_RETRIES; i++) {
        try {
          const result = await probeBackend();
          if (!mountedRef.current || cancelled) return;
          setMessage(result.message);
          setState(result.state);
          return;
        } catch {
          if (!mountedRef.current || cancelled) return;
          if (i >= INITIAL_RETRIES - 1) {
            setState("disconnected");
            return;
          }
          await new Promise((r) => setTimeout(r, RETRY_DELAY));
        }
      }
    };

    check();
    const interval = setInterval(() => {
      check();
    }, POLL_INTERVAL);

    return () => {
      cancelled = true;
      mountedRef.current = false;
      clearInterval(interval);
    };
  }, []);

  const dot = {
    checking: "bg-gray-400",
    connected: "bg-green-500",
    degraded: "bg-amber-500",
    disconnected: "bg-red-500",
  }[state];

  const label = backendStateLabel(state, message);

  const title = t(message ?? label);

  return (
    <span className="flex items-center gap-1.5 text-xs text-text-muted" title={title}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dot}`} />
      {t(label)}
    </span>
  );
}
