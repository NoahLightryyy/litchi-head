import { debateLimitations, type DebateNoticeInput } from "@/lib/debate-limitations";

export function DebateDataNotice({ result }: { result: DebateNoticeInput }) {
  const notice = debateLimitations(result);
  if (!notice.highlights.length) return null;
  return (
    <section aria-label="本次分析的数据说明" className="mb-4 rounded-md border border-bg-tertiary bg-bg-secondary p-4 text-sm">
      <h4 className="font-semibold text-text-primary">本次分析的数据说明</h4>
      <ul className="mt-3 space-y-2">
        {notice.highlights.map((item, index) => (
          <li key={`${item.label}:${index}`} className={item.tone === "danger"
            ? "rounded-md bg-accent-red/10 p-2 text-accent-red"
            : item.tone === "warning" ? "rounded-md bg-amber-500/10 p-2 text-amber-800 dark:text-amber-300" : "text-text-secondary"}>
            <span className="font-medium">{item.label}：</span>{item.message}
          </li>
        ))}
      </ul>
      {notice.researchOnly && <p className="mt-3 text-xs text-text-muted">本次为研究结果，未生成交易执行指令。</p>}
      {notice.diagnostics.length > 0 && (
        <details className="mt-3 border-t border-bg-tertiary pt-3 text-text-muted">
          <summary className="cursor-pointer text-xs">查看来源与诊断详情</summary>
          <div className="mt-3 space-y-4">
            {notice.diagnostics.map((item) => (
              <div key={item.capability} className="space-y-2 text-xs">
                <p className="font-medium">{item.label} · {item.capability}</p>
                {item.notes.length ? item.notes.map((note) => <p key={note} className="whitespace-pre-wrap break-words leading-6">{note}</p>)
                  : <p>此历史结果未保存进一步的范围说明。</p>}
                {item.sources.length > 0 && <ul className="space-y-1 break-words">{item.sources.map((source) => <li key={source}>{source}</li>)}</ul>}
                {item.codes.length > 0 && <p className="break-words">诊断代码：{item.codes.join("、")}</p>}
              </div>
            ))}
          </div>
        </details>
      )}
    </section>
  );
}
