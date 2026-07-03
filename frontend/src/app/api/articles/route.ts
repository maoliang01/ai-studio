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
 * 转换文章列表的字段名
 */
function convertArticleItem(item: Record<string, unknown>): Record<string, unknown> {
  const converted = toCamelCase(item);
  // 保留原始的下划线字段（兼容）
  return {
    ...converted,
    sourceId: item.source_id,
    sourceName: item.source_name,
    categoryId: item.category_id,
    categoryName: item.category_name,
    publishedAt: item.published_at,
  };
}

// 获取文章列表
export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());

    const res = await fetch(`${BACKEND_URL}/api/articles?${new URLSearchParams(params)}`);
    const data = await res.json();

    // 转换文章列表的字段名
    if (data.items && Array.isArray(data.items)) {
      data.items = data.items.map((item: Record<string, unknown>) => convertArticleItem(item));
    }

    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}