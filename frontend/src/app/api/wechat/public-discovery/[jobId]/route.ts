import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

export async function GET(_request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  try {
    const { jobId } = await params;
    const response = await fetch(
      `${BACKEND_URL}/api/wechat/public-discovery/${encodeURIComponent(jobId)}`,
      { cache: "no-store" },
    );
    const body = await response.text();
    return new NextResponse(body, {
      status: response.status,
      headers: { "Content-Type": response.headers.get("content-type") || "application/json" },
    });
  } catch (error) {
    console.error("获取公开来源发现任务失败:", error);
    return NextResponse.json({ error: "获取公开来源发现任务失败" }, { status: 500 });
  }
}
