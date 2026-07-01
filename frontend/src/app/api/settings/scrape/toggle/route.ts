import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

// 切换爬取源启用状态
export async function POST(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const sourceId = searchParams.get("id");
    const res = await fetch(`${BACKEND_URL}/settings/scrape/${sourceId}/toggle`, {
      method: "POST",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to toggle scrape source" }, { status: 500 });
  }
}