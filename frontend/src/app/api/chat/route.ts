import { NextResponse } from "next/server";

// 使用服务端变量，不会暴露到浏览器
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// 对话 API
export async function POST(request: Request) {
  try {
    const body = await request.json();
    // 获取取消信号
    const signal = request.signal;

    // 在服务器端转发请求到后端（带取消支持）
    const res = await fetch(`${BACKEND_URL}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal,
    });

    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return NextResponse.json({ error: "请求已取消" }, { status: 499 });
    }
    console.error("Chat API error:", error);
    return NextResponse.json({ error: "Chat failed" }, { status: 500 });
  }
}