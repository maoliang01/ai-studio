import { NextResponse } from "next/server";

// 从配置的爬取源爬取
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${process.env.BACKEND_URL || "http://localhost:8080"}/scrape/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "从爬取源爬取失败", details: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}

// 获取爬取源列表
export async function GET() {
  try {
    const res = await fetch(`${process.env.BACKEND_URL || "http://localhost:8080"}/scrape/sources`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json(
      { error: "获取爬取源失败", details: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}