"use client";

import Link from "next/link";
import { useLocale } from "./locale-provider";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  type BackendState,
  type DiagnoseResult,
  classifyBackendProbe,
  normalizeDataSourceDiagnostics,
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

/* ── 后端状态横幅（页面顶部） ── */
export function BackendStatusIndicator() {
  const { t } = useLocale();
  const [state, setState] = useState<BackendState>("checking");
  const mountedRef = useRef(true);

  const check = useCallback(async () => {
    for (let i = 0; i < INITIAL_RETRIES; i++) {
      try {
        const result = await probeBackend();
        if (!mountedRef.current) return;
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

  // 降级详情集中到数据状态页；顶部状态入口持续保留真实状态。

  return null;
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

  const label = {
    checking: "连接中",
    connected: "已连接",
    degraded: message ? "诊断不可用" : "部分异常",
    disconnected: "未连接",
  }[state];

  const title = t(message ?? label);

  return (
    <Link href="/data-status" className="flex items-center gap-1.5 text-xs text-text-muted hover:text-text-primary" title={title} aria-label={`${t("数据状态")}: ${t(label)}`}>
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${dot}`} />
      {t(label)}
    </Link>
  );
}
