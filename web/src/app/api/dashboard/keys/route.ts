import { NextRequest, NextResponse } from "next/server";
import { getOrgContext, proxyGet, proxyPost, hasActiveSubscription } from "@/lib/server-auth";

// GET /api/dashboard/keys — list org's API keys
export async function GET() {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { status, body } = await proxyGet("/v1/keys/list", ctx);
  return NextResponse.json(body, { status });
}

// POST /api/dashboard/keys — create a new API key (requires active Stripe subscription)
export async function POST(req: NextRequest) {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Gate: must have active Stripe subscription (payment on file)
  const paid = await hasActiveSubscription(ctx.orgId);
  if (!paid) {
    return NextResponse.json(
      {
        error: "payment_required",
        message:
          "A payment method is required before creating API keys. Please add your credit card to get started.",
      },
      { status: 402 }
    );
  }

  let body: { name?: string };
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const { status, body: responseBody } = await proxyPost("/v1/keys/create", ctx, {
    name: body.name || "Default",
  });
  return NextResponse.json(responseBody, { status });
}

// DELETE /api/dashboard/keys?key_id=... — revoke a key
export async function DELETE(req: NextRequest) {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const keyId = req.nextUrl.searchParams.get("key_id");
  if (!keyId) return NextResponse.json({ error: "key_id required" }, { status: 400 });

  const { status, body } = await proxyPost(`/v1/keys/${keyId}/revoke`, ctx, {});
  return NextResponse.json(body, { status });
}
