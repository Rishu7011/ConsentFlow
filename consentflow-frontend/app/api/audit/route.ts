import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/constants";

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const res = await fetch(`${BACKEND_URL}/audit/trail${url.search}`, {
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}
