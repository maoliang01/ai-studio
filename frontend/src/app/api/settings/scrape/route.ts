import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// 获取所有爬取源
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/settings/scrape`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to fetch scrape sources" }, { status: 500 });
  }
}

// 添加爬取源
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/settings/scrape`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to add scrape source" }, { status: 500 });
  }
}

// 更新爬取源
export async function PUT(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const sourceId = searchParams.get("id");
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/settings/scrape/${sourceId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to update scrape source" }, { status: 500 });
  }
}

// 删除爬取源
export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const sourceId = searchParams.get("id");
    const res = await fetch(`${BACKEND_URL}/settings/scrape/${sourceId}`, {
      method: "DELETE",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: "Failed to delete scrape source" }, { status: 500 });
  }
}