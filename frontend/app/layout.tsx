import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "./app-shell";

export const metadata: Metadata = {
  title: "litchi-head — AI 投资决策平台",
  description: "多智能体自上而下投资决策：宏观洞察 → 产业链分析 → AI 辩论决策",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="dark">
      <body className="antialiased">
        <Providers>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
