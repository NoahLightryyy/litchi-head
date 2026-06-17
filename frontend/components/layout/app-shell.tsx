"use client";

import { ReactNode } from "react";
import { SidebarNav } from "./sidebar-nav";
import { Header } from "./header";

interface AppShellProps {
  children: ReactNode;
}

/** 全局布局外壳：Sidebar + Header + main 内容区 */
export function AppShell({ children }: AppShellProps) {
  return (
    <div className="flex h-screen overflow-hidden bg-bg-primary">
      <SidebarNav />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
