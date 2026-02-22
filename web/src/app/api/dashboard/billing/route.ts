import { NextRequest, NextResponse } from "next/server";
import { getOrgContext, proxyGet, getCheckoutUrl, hasActiveSubscription } from "@/lib/server-auth";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";

// GET /api/dashboard/billing — billing status + payment status
export async function GET() {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const session = await auth.api.getSession({ headers: await headers() });

  const [billingRes, paid] = await Promise.all([
    proxyGet("/v1/billing/status", ctx),
    hasActiveSubscription(ctx.orgId),
  ]);

  return NextResponse.json({
    ...billingRes.body,
    has_payment_method: paid,
    org_id: ctx.orgId,
    plan: ctx.plan,
    email: session?.user.email ?? null,
  });
}

// POST /api/dashboard/billing/checkout — get Stripe checkout URL
export async function POST(req: NextRequest) {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const session = await auth.api.getSession({ headers: await headers() });

  let body: { product_id?: string; success_url?: string; cancel_url?: string };
  try {
    body = await req.json();
  } catch {
    body = {};
  }

  const productId = body.product_id ?? "paygo";
  const appUrl = process.env.NEXT_PUBLIC_APP_URL || "https://foundry-coral-six.vercel.app";
  const successUrl = body.success_url ?? `${appUrl}/dashboard?upgraded=1`;
  const cancelUrl = body.cancel_url ?? `${appUrl}/dashboard`;

  const checkoutUrl = await getCheckoutUrl(
    ctx.orgId,
    ctx.orgName,
    session?.user.email ?? null,
    productId,
    successUrl,
    cancelUrl
  );

  if (!checkoutUrl) {
    return NextResponse.json({ error: "Could not generate checkout URL" }, { status: 500 });
  }

  return NextResponse.json({ checkout_url: checkoutUrl });
}
