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
  options?: RequestInit
): Promise<T> {
  const url = `${BASE_URL}${endpoint}`;

  try {
    const res = await fetch(url, {
      headers: {
        "Content-Type": "application/json",
        ...options?.headers,
      },
      ...options,
    });

    const body = await res.json();

    if (!res.ok) {
      const err = body.error || {};
      throw new ApiError(
        err.code || "UNKNOWN",
        err.message || `HTTP ${res.status}`,
        res.status,
        err.detail
      );
    }

    return body.data !== undefined ? body.data : body;
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
  get: <T>(path: string, params?: Record<string, string>) => {
    const query = params
      ? "?" + new URLSearchParams(params).toString()
      : "";
    return request<T>(`${path}${query}`);
  },

  post: <T>(path: string, data?: unknown) => {
    return request<T>(path, {
      method: "POST",
      body: data ? JSON.stringify(data) : undefined,
    });
  },
};
