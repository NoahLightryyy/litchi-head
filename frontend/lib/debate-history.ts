/** Choose a persisted result without relabelling an old result as a new analysis. */
export function selectDebateView(
  records: {session_id: string; stock_code: string; status: string}[],
  stockCode: string,
  selectedId: string | null,
  currentId: string | null,
  triggered: boolean,
): { sessionId: string | null; historical: boolean } {
  const completed = records.filter(record => record.stock_code === stockCode && record.status === "completed");
  const selected = completed.find(record => record.session_id === selectedId);
  if (selected) return {sessionId: selected.session_id, historical: true};
  if (currentId) return {sessionId: currentId, historical: false};
  if (!triggered) {
    const matching = records.filter(record => record.stock_code === stockCode);
    const active = matching.find(record => record.status === "running" || record.status === "queued");
    if (active) return {sessionId: active.session_id, historical: false};
    if (matching[0]?.status === "failed") return {sessionId: matching[0].session_id, historical: false};
  }
  if (!triggered && completed.length) return {sessionId: completed[0].session_id, historical: true};
  return {sessionId: null, historical: false};
}
