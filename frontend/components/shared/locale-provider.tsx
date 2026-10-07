"use client";

import { createContext, useContext, useState } from "react";
import { LOCALE_COOKIE, translate, type Locale } from "@/lib/locale";

const LocaleContext = createContext<{
  locale: Locale; setLocale: (value: Locale) => void; t: (text: string) => string; saved: boolean;
} | null>(null);

export function LocaleProvider({ initialLocale, children }: { initialLocale: Locale; children: React.ReactNode }) {
  const [locale, updateLocale] = useState(initialLocale);
  const [saved, setSaved] = useState(true);
  const setLocale = (value: Locale) => {
    updateLocale(value);
    document.documentElement.lang = value;
    document.title = `litchi-head — ${translate(value, "AI 投资决策平台")}`;
    try {
      document.cookie = `${LOCALE_COOKIE}=${value}; Path=/; Max-Age=31536000; SameSite=Lax`;
      setSaved(document.cookie.split(";").some(item => item.trim() === `${LOCALE_COOKIE}=${value}`));
    } catch { setSaved(false); }
  };
  return <LocaleContext.Provider value={{locale,setLocale,t: text => translate(locale,text),saved}}>{children}</LocaleContext.Provider>;
}

export function useLocale() {
  const value = useContext(LocaleContext);
  if (!value) throw new Error("useLocale requires LocaleProvider");
  return value;
}

export function LanguageSelect() {
  const {locale,setLocale,t,saved} = useLocale();
  return <div className="px-1 sm:px-3 text-xs text-text-muted">
    <label htmlFor="interface-language" className="block mb-2"><span aria-hidden="true">🌐 </span><span className="hidden sm:inline">语言 / Language</span></label>
    <select id="interface-language" aria-label="语言 / Language" value={locale} onChange={event=>setLocale(event.target.value === "en" ? "en" : "zh-CN")} className="w-full min-w-0 rounded-md border border-bg-tertiary bg-bg-primary px-1 sm:px-2 py-2 text-text-primary">
      <option value="zh-CN" lang="zh-CN">中文</option><option value="en" lang="en">English</option>
    </select>
    {!saved && <p role="status" className="mt-2">{t("语言偏好仅在本次页面生效，浏览器未允许保存。")}</p>}
  </div>;
}
