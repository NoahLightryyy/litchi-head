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
  if (!triggered && completed.length) return {sessionId: completed[0].session_id, historical: true};
  return {sessionId: null, historical: false};
}
