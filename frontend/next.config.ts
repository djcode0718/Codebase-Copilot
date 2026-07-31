import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  devIndicators: false,
  allowedDevOrigins: ['172.24.96.1', 'localhost', '127.0.0.1'],
};

export default nextConfig;
