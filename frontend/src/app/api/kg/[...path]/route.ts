import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8500";
export const maxDuration = 200;

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
    const { searchParams } = new URL(request.url);
    const queryString = searchParams.toString();

    // body 容错:前端调 reconcile/batch-process 时往往没有 body
    let body: string | undefined;
    const raw = await request.text();
    if (raw) {
      try {
        JSON.parse(raw); // 校验 JSON 合法
        body = raw;
      } catch {
        body = undefined; // 非 JSON 一律当空 body
      }
    }

    const backendPath = path.join("/");
    const baseUrl = `${BACKEND_URL}/api/kg/${backendPath}`;
    const url = queryString ? `${baseUrl}?${queryString}` : baseUrl;

    const fetchOpts: RequestInit = {
      method: "POST",
      headers: body ? { "Content-Type": "application/json" } : {},
    };
    if (body) fetchOpts.body = body;

    const res = await fetch(url, fetchOpts);
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
