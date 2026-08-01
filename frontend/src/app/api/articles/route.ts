import { NextResponse } from "next/server";
import { normalizeArticleResponse } from "./normalize";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const params = Object.fromEntries(searchParams.entries());
    const res = await fetch(`${BACKEND_URL}/api/articles?${new URLSearchParams(params)}`);
    const data = await res.json();

    return NextResponse.json(normalizeArticleResponse(data));
  } catch (error) {
    return NextResponse.json(
      { error: error instanceof Error ? error.message : "未知错误" },
      { status: 500 }
    );
  }
}
