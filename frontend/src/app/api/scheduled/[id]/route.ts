import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

/**
 * 将 snake_case 键转换为 camelCase（修复数组处理）
 */
function toCamelCase(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(item => toCamelCase(item));
  if (typeof obj !== "object") return obj;

  return Object.keys(obj as Record<string, unknown>).reduce((acc, key) => {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    const value = (obj as Record<string, unknown>)[key];
    // 递归处理嵌套对象，但不处理数组（数组在上面处理）
    acc[camelKey] = (typeof value === "object" && value !== null && !Array.isArray(value))
      ? toCamelCase(value)
      : value;
    return acc;
  }, {} as Record<string, unknown>);
}

/**
 * 安全解析 JSON
 */
async function safeJsonParse(res: Response): Promise<unknown> {
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    return { error: text || `HTTP ${res.status}` };
  }
}

/**
 * 获取单个定时任务
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/api/scheduled/${id}`);
    const data = await safeJsonParse(res);

    if (!res.ok) {
      return NextResponse.json({ error: (data as any).detail || "获取失败" }, { status: res.status });
    }

    return NextResponse.json(toCamelCase(data));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}

/**
 * 更新定时任务
 */
export async function PUT(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
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

    const res = await fetch(`${BACKEND_URL}/api/scheduled/${id}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await safeJsonParse(res);
    if (!res.ok) {
      return NextResponse.json({ error: (data as any).detail || "更新失败" }, { status: res.status });
    }

    return NextResponse.json(toCamelCase(data));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}

/**
 * 删除定时任务
 */
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/api/scheduled/${id}`, {
      method: "DELETE",
    });

    if (!res.ok) {
      const data = await safeJsonParse(res);
      return NextResponse.json({ error: (data as any).detail || "删除失败" }, { status: res.status });
    }

    return NextResponse.json({ message: "删除成功" });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}