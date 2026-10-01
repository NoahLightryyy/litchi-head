/* ── HTTP 客户端封装 ── */

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";

export class ApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public status: number,
    public detail?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(
  endpoint: string,
  options?: RequestInit,
  unwrapData: boolean = true,
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
    });

    const body = await res.json();

    if (!res.ok) {
      const err = body.error || {};
      throw new ApiError(
        err.code || "UNKNOWN",
        err.message || `HTTP ${res.status}`,
        res.status,
        err.detail ?? body.meta
      );
    }

    return unwrapData && body.data !== undefined ? body.data : body;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      "NETWORK_ERROR",
      "网络请求失败，请检查后端服务是否运行",
      0
    );
  }
}

export const api = {
  get: <T>(path: string, params?: Record<string, string>, options?: RequestInit) => {
    const query = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    return request<T>(`${path}${query}`, options);
  },

  getRaw: <T>(path: string, params?: Record<string, string>, options?: RequestInit) => {
    const query = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    return request<T>(`${path}${query}`, options, false);
  },

  post: <T>(path: string, data?: unknown) => {
    return request<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  },

  postRaw: <T>(path: string, data: unknown, options?: RequestInit) => request<T>(path, {
    ...options, method: "POST", body: JSON.stringify(data),
  }, false),

  put: <T>(path: string, data?: unknown) => {
    return request<T>(path, {
      method: "PUT",
      body: data ? JSON.stringify(data) : undefined,
    });
  },

  del: <T>(path: string) => {
    return request<T>(path, {
      method: "DELETE",
    });
  },
};
