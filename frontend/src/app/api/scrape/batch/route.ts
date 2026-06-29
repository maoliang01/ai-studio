import { NextResponse } from "next/server";

// 批量爬取多个 URL
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${process.env.BACKEND_URL || "http://localhost:8000"}/scrape/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "批量爬取失败", details: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}