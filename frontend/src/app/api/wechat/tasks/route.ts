import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

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

// 获取定时任务列表
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());

    const res = await fetch(`${BACKEND_URL}/api/wechat/tasks?${new URLSearchParams(params)}`);
    const data = await res.json();

    // 转换字段名
    if (data.items && Array.isArray(data.items)) {
      data.items = data.items.map((item: Record<string, unknown>) => toCamelCase(item));
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("获取定时任务列表失败:", error);
    return NextResponse.json(
      { error: "获取定时任务列表失败" },
      { status: 500 }
    );
  }
}

// 创建定时任务
export async function POST(request: Request) {
  try {
    const body = await request.json();

    const res = await fetch(`${BACKEND_URL}/api/wechat/tasks`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    const data = await res.json();

    if (data.item) {
      data.item = toCamelCase(data.item);
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error("创建定时任务失败:", error);
    return NextResponse.json(
      { error: "创建定时任务失败" },
      { status: 500 }
    );
  }
}
