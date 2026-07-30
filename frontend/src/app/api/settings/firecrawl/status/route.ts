import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

// 获取 Firecrawl 服务状态
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/settings/firecrawl/status`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ is_running: false, error: "Failed to check status" }, { status: 500 });
  }
}