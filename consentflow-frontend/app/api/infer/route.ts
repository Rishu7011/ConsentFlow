import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/constants";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const uid = req.headers.get("X-User-ID");
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (uid) headers["X-User-ID"] = uid;
    const res = await fetch(`${BACKEND_URL}/infer/predict`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}
