import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// 切换爬取源启用状态
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params;
    const res = await fetch(`${BACKEND_URL}/settings/scrape/${id}/toggle`, {
      method: "POST",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "切换状态失败", details: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}