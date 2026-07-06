import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";

/**
 * 知识图谱 API 代理 (catch-all 路由)
 *
 * 将前端请求转发到后端:
 * /api/kg/health -> backend/api/kg/health
 * /api/kg/graph?limit=500 -> backend/api/kg/graph?limit=500
 * /api/kg/process/123 -> backend/api/kg/process/123
 */

// GET 请求
export async function GET(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path } = await params;
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();

    const backendPath = path.join("/");
    const url = queryString
      ? `${BACKEND_URL}/api/kg/${backendPath}?${queryString}`
      : `${BACKEND_URL}/api/kg/${backendPath}`;

    const res = await fetch(url);
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("KG API GET error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}

// POST 请求
export async function POST(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path } = await params;
    const body = await request.json();

    const backendPath = path.join("/");
    const url = `${BACKEND_URL}/api/kg/${backendPath}`;

    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("KG API POST error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}

// DELETE 请求
export async function DELETE(
  request: Request,
  { params }: { params: Promise<{ path: string[] }> }
) {
  try {
    const { path } = await params;
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();

    const backendPath = path.join("/");
    const url = `${BACKEND_URL}/api/kg/${backendPath}${queryString ? `?${queryString}` : ""}`;

    const res = await fetch(url, {
      method: "DELETE",
    });
    const data = await res.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("KG API DELETE error:", error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}