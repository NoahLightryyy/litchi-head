export const RANKING_PAGE_SIZE = 10;

/** Page the received ranking without changing its source order or dropping the tail. */
export function rankingPage<T>(rows: readonly T[], requestedPage: number) {
  const pageCount = Math.max(1, Math.ceil(rows.length / RANKING_PAGE_SIZE));
  const page = Math.min(pageCount, Math.max(1, Math.floor(requestedPage) || 1));
  const offset = (page - 1) * RANKING_PAGE_SIZE;
  return { items: rows.slice(offset, offset + RANKING_PAGE_SIZE), page, pageCount,
    total: rows.length, start: rows.length ? offset + 1 : 0,
    end: Math.min(offset + RANKING_PAGE_SIZE, rows.length) };
}
