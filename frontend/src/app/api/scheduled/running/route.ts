import { NextResponse } from "next/server";

// 获取运行中的任务
export async function GET() {
  try {
    const response = await fetch(`${process.env.BACKEND_URL}/api/scheduled/running`);
    if (!response.ok) {
      return NextResponse.json({ error: "获取运行中任务失败" }, { status: response.status });
    }
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Failed to fetch running tasks:", error);
    return NextResponse.json({ error: "获取运行中任务失败" }, { status: 500 });
  }
}