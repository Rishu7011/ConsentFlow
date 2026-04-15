import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/constants";

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const uid = req.headers.get("X-User-ID");
    const headers: Record<string, string> = {};
    if (uid) headers["X-User-ID"] = uid;
    const res = await fetch(`${BACKEND_URL}/chat/history${url.search}`, {
      headers,
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}
