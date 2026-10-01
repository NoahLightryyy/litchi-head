import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* 前端在 localhost:3000，后端在 localhost:8000 */
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_API_URL || "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
