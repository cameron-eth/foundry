import { NextRequest, NextResponse } from "next/server";
import { getOrgContext, FOUNDRY_API_URL } from "@/lib/server-auth";

// POST /api/dashboard/tools/invoke — invoke a tool by tool_id
export async function POST(req: NextRequest) {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  let body: { tool_id?: string; input?: Record<string, unknown> };
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const { tool_id, input = {} } = body;
  if (!tool_id) return NextResponse.json({ error: "tool_id required" }, { status: 400 });

  const res = await fetch(`${FOUNDRY_API_URL}/v1/tools/${tool_id}/invoke`, {
    method: "POST",
    headers: {
      "X-API-Key": ctx.apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ input }),
  });

  const responseBody = await res.json().catch(() => ({}));
  return NextResponse.json(responseBody, { status: res.status });
}
