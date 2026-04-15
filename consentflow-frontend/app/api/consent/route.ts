import { NextRequest, NextResponse } from "next/server";
import { BACKEND_URL } from "@/lib/constants";

function buildHeaders(req: NextRequest) {
  const h: Record<string, string> = { "Content-Type": "application/json" };
  const uid = req.headers.get("X-User-ID");
  if (uid) h["X-User-ID"] = uid;
  return h;
}

export async function GET(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const res = await fetch(`${BACKEND_URL}/consent${url.search}`, {
      headers: buildHeaders(req),
      cache: "no-store",
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const res = await fetch(`${BACKEND_URL}/consent`, {
      method: "POST",
      headers: buildHeaders(req),
      body: JSON.stringify(body),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}

export async function DELETE(req: NextRequest) {
  try {
    const url = new URL(req.url);
    const res = await fetch(`${BACKEND_URL}/consent${url.search}`, {
      method: "DELETE",
      headers: buildHeaders(req),
    });
    const data = await res.json();
    return NextResponse.json(data, { status: res.status });
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 503 });
  }
}
