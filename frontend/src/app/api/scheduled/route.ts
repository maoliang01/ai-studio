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

/**
 * 安全解析 JSON，处理非 JSON 响应
 */
async function safeJsonParse(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    // 如果不是 JSON，返回原始文本或错误对象
    return { error: text || `HTTP ${res.status}` };
  }
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
    const data = await safeJsonParse(res);

    if (Array.isArray(data)) {
      return NextResponse.json(data.map((item: Record<string, unknown>) => toCamelCase(item)));
    }
    return NextResponse.json(data, { status: res.status });
  } catch (error) {
    return NextResponse.json({ error: error instanceof Error ? error.message : "未知错误" }, { status: 500 });
  }
}

/**
 * 创建定时任务
 */
export async function POST(request: Request) {
  try {
    const body = await request.json();
    console.log("[API] POST /api/scheduled 收到数据:", JSON.stringify(body));

    // 转换为 snake_case（同时支持 camelCase 和 snake_case 格式）
    const payload: Record<string, unknown> = {};
    if (body.name !== undefined) payload.name = body.name;
    if (body.sourceIds !== undefined) payload.source_ids = body.sourceIds;
    else if (body.source_ids !== undefined) payload.source_ids = body.source_ids;
    if (body.sourceId !== undefined) payload.source_id = body.sourceId;
    else if (body.source_id !== undefined) payload.source_id = body.source_id;
    if (body.customUrl !== undefined) payload.custom_url = body.customUrl;
    else if (body.custom_url !== undefined) payload.custom_url = body.custom_url;
    if (body.scheduleTime !== undefined) payload.schedule_time = body.scheduleTime;
    else if (body.schedule_time !== undefined) payload.schedule_time = body.schedule_time;
    if (body.scrapeRange !== undefined) payload.scrape_range = body.scrapeRange;
    else if (body.scrape_range !== undefined) payload.scrape_range = body.scrape_range;
    if (body.isEnabled !== undefined) payload.is_enabled = body.isEnabled;
    else if (body.is_enabled !== undefined) payload.is_enabled = body.is_enabled;

    console.log("[API] 发送到后端:", JSON.stringify(payload));

    const res = await fetch(`${BACKEND_URL}/api/scheduled`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await safeJsonParse(res);
    console.log("[API] 后端响应:", res.status, JSON.stringify(data));

    if (!res.ok) {
      return NextResponse.json(
        { error: (data as any).detail || (data as any).error || "创建失败" },
        { status: res.status }
      );
    }

    return NextResponse.json(toCamelCase(data as Record<string, unknown>));
  } catch (error) {
    console.error("[API] POST /api/scheduled 错误:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}