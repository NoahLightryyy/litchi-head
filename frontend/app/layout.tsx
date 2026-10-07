import { cookies } from "next/headers";
import { LOCALE_COOKIE, normalizeLocale, translate } from "@/lib/locale";
import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { AppShell } from "./app-shell";

export async function generateMetadata(): Promise<Metadata> {
  const locale = normalizeLocale((await cookies()).get(LOCALE_COOKIE)?.value);
  return {title: `litchi-head — ${translate(locale, "AI 投资决策平台")}`};
}

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = normalizeLocale((await cookies()).get(LOCALE_COOKIE)?.value);
  return (
    <html lang={locale} className="dark">
      <body className="antialiased">
        <Providers initialLocale={locale}>
          <AppShell>{children}</AppShell>
        </Providers>
      </body>
    </html>
  );
}
