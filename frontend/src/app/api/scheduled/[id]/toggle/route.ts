import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

/**
 * 将 snake_case 键转换为 camelCase
 */
function toCamelCase(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(item => toCamelCase(item));
  if (typeof obj !== "object") return obj;

  return Object.keys(obj as Record<string, unknown>).reduce((acc, key) => {
    const camelKey = key.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase());
    const value = (obj as Record<string, unknown>)[key];
    acc[camelKey] = (typeof value === "object" && value !== null && !Array.isArray(value))
      ? toCamelCase(value)
      : value;
    return acc;
  }, {} as Record<string, unknown>);
}

/**
 * 切换任务启用状态
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/api/scheduled/${id}/toggle`, {
      method: "POST",
    });

    const text = await res.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      return NextResponse.json(
        { error: text || `HTTP ${res.status}` },
        { status: res.status }
      );
    }

    if (!res.ok) {
      return NextResponse.json(
        { error: (data as any).detail || "切换失败" },
        { status: res.status }
      );
    }

    return NextResponse.json(toCamelCase(data));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}
