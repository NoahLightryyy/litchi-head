"use client";

import { useState, useEffect, useSyncExternalStore } from "react";
import { BackendStatusIndicator, HeaderStatusDot } from "@/components/shared/backend-status";
import { usePathname } from "next/navigation";
import Link from "next/link";

/* ── 路径 → 标题 映射 ── */
function useRouteMeta(pathname: string): { title: string } {
  if (pathname === "/") return { title: "市场总览" };
  if (pathname === "/industries") return { title: "行业研究" };
  if (pathname === "/retro") return { title: "研究与复盘" };
  if (pathname.startsWith("/sector/"))
    return { title: `板块 · ${pathname.slice(8)}` };
  if (pathname.startsWith("/stock/"))
    return { title: `个股 · ${pathname.slice(7)}` };
  return { title: pathname };
}

/** 全局网络状态 */
function subscribeToOnlineStatus(onStoreChange: () => void): () => void {
  window.addEventListener("online", onStoreChange);
  window.addEventListener("offline", onStoreChange);
  return () => {
    window.removeEventListener("online", onStoreChange);
    window.removeEventListener("offline", onStoreChange);
  };
}

function useOnlineStatus(): boolean {
  return useSyncExternalStore(
    subscribeToOnlineStatus,
    () => navigator.onLine,
    () => true,
  );
}

/** 客户端交互外壳（布局逻辑、导航高亮、加载进度条、离线检测） */
export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const meta = useRouteMeta(pathname);
  const online = useOnlineStatus();

  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <SidebarNav pathname={pathname} />
      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {!online && (
          <div className="px-4 py-2 bg-accent-red/10 text-accent-red text-xs text-center border-b border-accent-red/20">
            ⚠ 网络已断开，数据可能无法更新
          </div>
        )}
        <BackendStatusIndicator />
        <LoadingBar />
        <Header meta={meta} />
        <main className="flex-1 overflow-y-auto p-3 sm:p-6">{children}</main>
      </div>
    </div>
  );
}

/* ── 全局顶部加载进度条 ── */
function LoadingBar() {
  const pathname = usePathname();
  const [settledPath, setSettledPath] = useState(pathname);
  const loading = settledPath !== pathname;

  useEffect(() => {
    const timer = setTimeout(() => setSettledPath(pathname), 400);
    return () => clearTimeout(timer);
  }, [pathname]);

  return (
    <div className="h-0.5 bg-bg-primary relative overflow-hidden">
      <div
        className={`absolute inset-0 bg-accent-blue transition-all duration-300 ease-out ${
          loading ? "w-4/5 opacity-100" : "w-0 opacity-0"
        }`}
      />
    </div>
  );
}

/* ── 侧边栏导航 ── */
const STOCK_PREFIX = "/stock/";
const SECTOR_PREFIX = "/sector/";

function SidebarNav({ pathname }: { pathname: string }) {
  const navItems = [
    { href: "/", icon: "🏠", label: "市场总览" },
    { href: "/industries", icon: "🧭", label: "行业研究" },
    { href: "/retro", icon: "📋", label: "研究与复盘" },
  ];

  return (
    <aside className="w-16 sm:w-56 border-r border-bg-tertiary bg-bg-secondary p-2 sm:p-4 flex flex-col gap-6 shrink-0">
      <div className="flex items-center gap-2 px-2">
        <span className="text-2xl">🍒</span>
        <span className="hidden sm:block font-bold text-lg text-text-primary tracking-tight">
          litchi-head
        </span>
      </div>
      <nav className="flex flex-col gap-1">
        {navItems.map((item) => {
          const active = item.href === "/" ? pathname === "/" : (pathname === item.href || (item.href === "/industries" && pathname.startsWith("/sector/")));
          return (
            <Link
              key={item.label}
              href={item.href}
              aria-current={active ? "page" : undefined}
              aria-label={item.label}
              title={item.label}
              className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-accent-blue/10 text-accent-blue font-medium"
                  : "text-text-secondary hover:bg-bg-tertiary hover:text-text-primary"
              }`}
            >
              <span>{item.icon}</span>
              <span className="hidden sm:inline">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto hidden sm:block">
        <div className="px-3 py-2 text-xs text-text-muted uppercase tracking-wider">最近浏览</div>
        <div className="px-3 py-4 text-xs text-text-muted text-center">
          {pathname.startsWith(STOCK_PREFIX) || pathname.startsWith(SECTOR_PREFIX) ? (
            <span className="text-accent-blue text-[10px] break-all">{pathname}</span>
          ) : (
            "暂无记录"
          )}
        </div>
      </div>
    </aside>
  );
}

/* ── 顶部栏 ── */
function Header({ meta }: { meta: { title: string } }) {
  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-bg-tertiary bg-bg-secondary shrink-0">
      <div className="flex items-center gap-3 text-sm text-text-secondary">
        <span className="text-text-muted">/</span>
        <span className="text-text-primary font-medium">{meta.title}</span>
      </div>
      <div className="flex items-center gap-4">
        <HeaderStatusDot />
        <span className="text-xs text-text-muted">数据来源: akshare</span>
      </div>
    </header>
  );
}
