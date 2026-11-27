import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const internalApiBase = (
      process.env.INTERNAL_API_URL || "http://127.0.0.1:8000/api/v1"
    ).replace(/\/+$/, "");
    return [
      {
        source: "/api/backend/:path*",
        destination: `${internalApiBase}/:path*`,
      },
    ];
  },
};

export default nextConfig;
