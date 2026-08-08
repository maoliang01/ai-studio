import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

/**
 * 将 snake_case 键转换为 camelCase
 */
function toCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  if (obj === null || typeof obj !== "object") return obj;
  if (Array.isArray(obj)) return obj.map(item =>
    typeof item === "object" ? toCamelCase(item as Record<string, unknown>) : item
  ) as unknown as Record<string, unknown>;

  return Object.keys(obj).reduce((acc, key) => {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    const value = obj[key];
    acc[camelKey] = typeof value === "object" && value !== null
      ? toCamelCase(value as Record<string, unknown>)
      : value;
    return acc;
  }, {} as Record<string, unknown>);
}

/**
 * 获取爬取历史记录
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());

    const res = await fetch(`${BACKEND_URL}/api/scheduled/history?${new URLSearchParams(params)}`);
    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "获取失败" }, { status: res.status });
    }

    if (Array.isArray(data)) {
      return NextResponse.json(data.map((item: Record<string, unknown>) => toCamelCase(item)));
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}