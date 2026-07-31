import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { id } = await params;
    const response = await fetch(`${BACKEND_URL}/api/wechat/cookies/${encodeURIComponent(id)}/deactivate`, { method: "POST" });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error("停用 Cookie 失败:", error);
    return NextResponse.json({ error: "停用 Cookie 失败" }, { status: 500 });
  }
}
