"use client";
import { restorePersonalRecords } from "@/lib/personal-backup";
import { parseResearchList } from "@/lib/research-list";
import { parseHoldings } from "@/lib/portfolio";
import { useState } from "react";
import { useResearchList } from "@/lib/hooks/use-research-list";
import { useHoldings } from "@/lib/hooks/use-holdings";
export default function SettingsPage() {
  const watch = useResearchList(); const holdings = useHoldings();
  const [message,setMessage] = useState("");
  const [pending,setPending] = useState<{watchlist: ReturnType<typeof parseResearchList>;holdings: ReturnType<typeof parseHoldings>} | null>(null);
  function backup() {
    const blob = new Blob([JSON.stringify({version:1,exportedAt:new Date().toISOString(),watchlist:watch.entries,holdings:holdings.entries},null,2)],{type:"application/json"});
    const url = URL.createObjectURL(blob); const anchor = document.createElement("a");
    anchor.href=url; anchor.download="litchi-personal-records.json"; anchor.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000); setMessage("备份文件已生成，请妥善保存，其中包含你的持仓和自选记录。");
  }
  return <div className="mx-auto max-w-3xl space-y-5"><h1 className="text-2xl font-semibold">设置</h1>
    <section className="rounded-lg border border-bg-tertiary bg-bg-secondary p-5 space-y-3"><h2 className="font-semibold">本机数据与备份</h2>
      <p className="text-sm text-text-muted">自选与手动持仓仅保存在当前浏览器、当前站点地址。更换端口或设备不会自动迁移；清理浏览器存储会丢失这些记录。研究复盘记录由后端保存，不包含在此备份中。</p>
      <p>自选 {watch.entries.length} 条 · 持仓 {holdings.entries.length} 条</p>
      {(watch.error || holdings.error) && <p role="alert" className="text-accent-red">{watch.error || holdings.error}</p>}
      <button disabled={!!watch.error || !!holdings.error} onClick={backup} className="rounded bg-accent-blue px-4 py-2 text-white disabled:opacity-40">导出本机记录备份</button><p role="status" className="text-sm">{message}</p>
      <label className="block text-sm">从备份文件恢复<input type="file" accept="application/json,.json" className="mt-2 block" onChange={async (event) => {
        setPending(null);
        const file=event.target.files?.[0]; if(!file) return;
        try {
          if(file.size>2000000) throw new Error("文件过大");
          const data=JSON.parse(await file.text());
          if(data.version!==1 || !Array.isArray(data.watchlist) || !Array.isArray(data.holdings)) throw new Error("格式无效");
          setPending({watchlist:parseResearchList(JSON.stringify(data.watchlist)),holdings:parseHoldings(JSON.stringify(data.holdings))});
          setMessage("备份校验通过，请核对数量后确认替换。");
        } catch { setMessage("备份格式无效或文件过大，原有数据未改动。"); }
      }} /></label>
      {pending && <div className="rounded border border-bg-tertiary p-3 text-sm"><p>将用文件中的 {pending.watchlist.length} 条自选、{pending.holdings.length} 条持仓替换本机对应记录。建议先导出当前备份。</p><button className="mt-2 rounded border border-accent-blue px-3 py-2 text-accent-blue" onClick={() => {
        try {
          restorePersonalRecords(localStorage,pending);
          window.dispatchEvent(new Event("litchi-research-list")); window.dispatchEvent(new Event("litchi-holdings")); setPending(null); setMessage("备份恢复完成");
        } catch (error) { setMessage(error instanceof Error ? error.message : "恢复失败"); }
      }}>确认替换并恢复</button><button className="ml-3" onClick={()=>setPending(null)}>取消</button></div>}
      <p className="text-sm text-text-muted">当前账户连接：未接入券商或支付宝；系统不保存交易密码，不发送订单。</p>
    </section>
  </div>;
}
