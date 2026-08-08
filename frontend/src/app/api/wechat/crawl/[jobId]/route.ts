import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

export async function GET(_request: Request, { params }: { params: Promise<{ jobId: string }> }) {
  try {
    const { jobId } = await params;
    const response = await fetch(`${BACKEND_URL}/api/wechat/crawl/status/${encodeURIComponent(jobId)}`, {
      cache: "no-store",
    });
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error("获取公众号爬取状态失败:", error);
    return NextResponse.json({ error: "获取公众号爬取状态失败" }, { status: 500 });
  }
}
