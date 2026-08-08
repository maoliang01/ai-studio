import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

async function forward(request: Request, id: string, method: "DELETE" | "PUT") {
  try {
    const init: RequestInit = { method };
    if (method === "PUT") {
      init.headers = { "Content-Type": "application/json" };
      init.body = JSON.stringify(await request.json());
    }
    const response = await fetch(`${BACKEND_URL}/api/wechat/cookies/${encodeURIComponent(id)}`, init);
    return NextResponse.json(await response.json(), { status: response.status });
  } catch (error) {
    console.error("Cookie 操作失败:", error);
    return NextResponse.json({ error: "Cookie 操作失败" }, { status: 500 });
  }
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  return forward(request, (await params).id, "DELETE");
}

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  return forward(request, (await params).id, "PUT");
}
