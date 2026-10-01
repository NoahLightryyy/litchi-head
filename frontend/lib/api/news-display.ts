import {parseNewsDisplay, type NewsDisplay} from "../news-display";

export class NewsDisplayError extends Error {
  constructor(message: string, public result?: NewsDisplay) { super(message); }
}
export async function fetchNewsDisplay(code: string, days: number, signal: AbortSignal): Promise<NewsDisplay> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api"}/stocks/${encodeURIComponent(code)}/news-display?days=${days}`, {signal});
  const body: unknown = await response.json();
  if (!response.ok && !(typeof body === "object" && body !== null && "schema_version" in body)) {
    throw new NewsDisplayError(response.status === 503 ? "检索服务暂时繁忙，请稍后重试" : "新闻检索请求失败");
  }
  const data = parseNewsDisplay(body, code);
  if (data.status === "failed" || !response.ok) throw new NewsDisplayError("新闻与公告检索未完成，请重试或稍后再看", data);
  return data;
}
