import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

/**
 * 获取每日爬取汇总（最近7天）
 */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/scheduled/history/summary`);
    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "获取失败" }, { status: res.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}