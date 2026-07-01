import { NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8080";

export async function GET(
    request: Request,
    { params }: { params: Promise<{ scrape_id: string }> }
) {
    try {
        const { scrape_id } = await params;
        const res = await fetch(`${BACKEND_URL}/scrape/progress/${scrape_id}`);
        const data = await res.json();
        return NextResponse.json(data);
    } catch (error) {
        return NextResponse.json(
            { status: "error", stage_name: "请求失败", stage_detail: String(error) },
            { status: 500 }
        );
    }
}