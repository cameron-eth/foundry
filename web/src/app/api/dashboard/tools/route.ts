import { NextRequest, NextResponse } from "next/server";
import { getOrgContext, proxyGet, proxyPost, hasActiveSubscription } from "@/lib/server-auth";

// GET /api/dashboard/tools — list org's tools
export async function GET() {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const { status, body } = await proxyGet("/v1/tools", ctx);
  return NextResponse.json(body, { status });
}

// POST /api/dashboard/tools — build a tool from description (requires payment)
export async function POST(req: NextRequest) {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  // Gate: must have active Stripe subscription
  const paid = await hasActiveSubscription(ctx.orgId);
  if (!paid) {
    return NextResponse.json(
      {
        error: "payment_required",
        message:
          "A payment method is required before building tools. Please add your credit card to get started.",
      },
      { status: 402 }
    );
  }

  let body: { description?: string; context?: string; async_build?: boolean };
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  if (!body.description) {
    return NextResponse.json({ error: "description is required" }, { status: 400 });
  }

  const { status, body: responseBody } = await proxyPost("/v1/construct", ctx, {
    capability_description: body.description,
    context: body.context,
    org_id: ctx.orgId,
    async_build: body.async_build ?? false, // sync by default in dashboard
    ttl_hours: 168, // 7 days
  });
  return NextResponse.json(responseBody, { status });
}
