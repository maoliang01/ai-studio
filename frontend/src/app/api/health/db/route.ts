import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

/** 将浏览器健康检查代理到 FastAPI，避免客户端依赖具体部署主机。 */
export async function GET() {
  try {
    const response = await fetch(`${BACKEND_URL}/health/db`, {
      cache: "no-store",
    });
    const data = await response.json();
    return NextResponse.json(data, { status: response.status });
  } catch (error) {
    return NextResponse.json(
      {
        status: "unhealthy",
        database: { connected: false },
        error: error instanceof Error ? error.message : "数据库健康检查失败",
      },
      { status: 503 },
    );
  }
}
