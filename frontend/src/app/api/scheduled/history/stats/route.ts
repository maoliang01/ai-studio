import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

/**
 * 获取任务统计
 */
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/api/scheduled/stats`);
    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "获取失败" }, { status: res.status });
    }

    // 转换为 camelCase
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(data)) {
      const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
      result[camelKey] = value;
    }

    return NextResponse.json(result);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}