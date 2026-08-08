import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

export async function POST(_: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const id = (await params).id;
    const response = await fetch(`${BACKEND_URL}/api/wechat/tasks/${encodeURIComponent(id)}/run`, { method: "POST" });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error("执行定时任务失败:", error);
    return NextResponse.json({ error: "执行定时任务失败" }, { status: 500 });
  }
}
