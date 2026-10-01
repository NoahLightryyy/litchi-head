import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 多轮分析会超过 Next 默认的 30 秒代理时限；保留后端真实响应。
  experimental: { proxyTimeout: 600_000 },
  /* 前端在 localhost:3000，后端在 localhost:8000 */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.LITCHI_BACKEND_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
