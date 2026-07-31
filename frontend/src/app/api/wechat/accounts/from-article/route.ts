import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

function toCamelCase(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(toCamelCase);
  if (!value || typeof value !== "object") return value;
  return Object.entries(value as Record<string, unknown>).reduce<Record<string, unknown>>((result, [key, item]) => {
    const camelKey = key.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
    result[camelKey] = toCamelCase(item);
    return result;
  }, {});
}

export async function POST(request: Request) {
  try {
    const response = await fetch(`${BACKEND_URL}/api/wechat/accounts/from-article`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(await request.json()),
    });
    return NextResponse.json(toCamelCase(await response.json()), { status: response.status });
  } catch (error) {
    console.error("从文章识别公众号失败:", error);
    return NextResponse.json({ error: "无法连接公众号识别服务" }, { status: 500 });
  }
}
