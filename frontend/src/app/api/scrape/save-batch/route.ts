import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

// 批量保存文章到数据库
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/scrape/save-batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const errorData = await res.json();
      return NextResponse.json(
        { success: false, error: errorData.detail || "保存失败" },
        { status: res.status }
      );
    }

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { success: false, error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}