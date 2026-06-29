import { NextResponse } from "next/server";

// 使用服务端变量，不会暴露到浏览器
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// 流式对话 API
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const signal = request.signal;

    // 在服务器端转发请求到后端，带取消支持
    const res = await fetch(`${BACKEND_URL}/chat/stream`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal, // 传递取消信号
    });

    // 如果请求被取消，返回空响应
    if (!res.ok && res.status === 499) {
      return new Response(null, { status: 499 });
    }

    // 直接传递流式响应
    return new Response(res.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") {
      return new Response(null, { status: 499 });
    }
    console.error("Stream API error:", error);
    return NextResponse.json({ error: "Stream failed" }, { status: 500 });
  }
}