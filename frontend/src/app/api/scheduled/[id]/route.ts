import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

/**
 * 将 snake_case 键转换为 camelCase
 */
function toCamelCase(obj: Record<string, unknown>): Record<string, unknown> {
  if (obj === null || typeof obj !== "object") return obj;
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
 * 获取单个定时任务
 */
export async function GET(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/api/scheduled/${id}`);
    const data = await res.json();

    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "获取失败" }, { status: res.status });
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

    const data = await res.json();
    if (!res.ok) {
      return NextResponse.json({ error: data.detail || "更新失败" }, { status: res.status });
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
      const data = await res.json();
      return NextResponse.json({ error: data.detail || "删除失败" }, { status: res.status });
    }

    return NextResponse.json({ message: "删除成功" });
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}