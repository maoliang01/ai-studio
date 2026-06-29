import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // 允许外网 IP 访问开发资源（解决跨域问题）
  allowedDevOrigins: ["114.118.5.16", "114.118.5.165"],
};

export default nextConfig;
