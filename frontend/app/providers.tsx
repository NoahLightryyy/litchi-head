"use client";

import { LocaleProvider } from "@/components/shared/locale-provider";
import type { Locale } from "@/lib/locale";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 15_000,
      refetchOnWindowFocus: false,
    },
  },
});

/** 全局客户端 Provider 封装 */
export function Providers({ children, initialLocale }: { children: React.ReactNode; initialLocale: Locale }) {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider initialLocale={initialLocale}>{children}</LocaleProvider>
    </QueryClientProvider>
  );
}
