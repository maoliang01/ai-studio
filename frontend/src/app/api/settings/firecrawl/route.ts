import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

// 获取 Firecrawl 配置
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/settings/firecrawl`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch Firecrawl config" }, { status: 500 });
  }
}

// 更新 Firecrawl 配置
export async function PUT(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/settings/firecrawl`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to update Firecrawl config" }, { status: 500 });
  }
}