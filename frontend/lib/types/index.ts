/* ── 通用类型 ── */

export interface ApiResponse<T> {
  data: T;
  meta: {
    cached: boolean;
    latency_ms: number;
  };
}

export interface ApiError {
  error: {
    code: string;
    message: string;
    detail?: unknown;
  };
}

export interface PaginatedResponse<T> extends ApiResponse<T[]> {
  meta: {
    cached: boolean;
    latency_ms: number;
    total: number;
    page: number;
    page_size: number;
  };
}
