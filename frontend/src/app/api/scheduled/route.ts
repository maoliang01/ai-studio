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

// ============ 定时任务 CRUD ============

/**
 * 获取定时任务列表
 */
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());
    const queryString = params.include_disabled ? `?${new URLSearchParams(params)}` : "";

    const res = await fetch(`${BACKEND_URL}/api/scheduled${queryString}`);
    const text = await res.text();

    // 尝试解析 JSON
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json([], { status: res.ok ? 200 : res.status });
    }

    if (Array.isArray(data)) {
      return NextResponse.json(data.map((item: Record<string, unknown>) => toCamelCase(item)));
    }
    return NextResponse.json([]);
  } catch (error) {
    return NextResponse.json([], { status: 500 });
  }
}

/**
 * 创建定时任务
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    // 转换为 snake_case
    const payload: Record<string, unknown> = {};
    if (body.name !== undefined) payload.name = body.name;
    if (body.sourceIds !== undefined) payload.source_ids = body.sourceIds;
    if (body.sourceId !== undefined) payload.source_id = body.sourceId;
    if (body.customUrl !== undefined) payload.custom_url = body.customUrl;
    if (body.scheduleTime !== undefined) payload.schedule_time = body.scheduleTime;
    if (body.scrapeRange !== undefined) payload.scrape_range = body.scrapeRange;
    if (body.isEnabled !== undefined) payload.is_enabled = body.isEnabled;

    const res = await fetch(`${BACKEND_URL}/api/scheduled`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "创建失败" }, { status: res.status });
    }

    return NextResponse.json(toCamelCase(data));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}