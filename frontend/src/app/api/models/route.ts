import { NextResponse } from "next/server";

// 使用服务端变量，不会暴露到浏览器
const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";

// 获取所有模型
export async function GET() {
  try {
    const res = await fetch(`${BACKEND_URL}/models`);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("GET models error:", error);
    return NextResponse.json({ error: "Failed to fetch models" }, { status: 500 });
  }
}

// 添加模型
export async function POST(request: Request) {
  try {
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/models`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("POST model error:", error);
    return NextResponse.json({ error: "Failed to add model" }, { status: 500 });
  }
}

// 更新模型
export async function PUT(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const modelId = searchParams.get("id");
    const body = await request.json();
    const res = await fetch(`${BACKEND_URL}/models/${modelId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("PUT model error:", error);
    return NextResponse.json({ error: "Failed to update model" }, { status: 500 });
  }
}

// 删除模型
export async function DELETE(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const modelId = searchParams.get("id");
    const res = await fetch(`${BACKEND_URL}/models/${modelId}`, {
      method: "DELETE",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("DELETE model error:", error);
    return NextResponse.json({ error: "Failed to delete model" }, { status: 500 });
  }
}