import { NextResponse } from "next/server";
import { getOrgContext, proxyGet } from "@/lib/server-auth";

export async function GET() {
  const ctx = await getOrgContext();
  if (!ctx) return NextResponse.json({ error: "Unauthorized" }, { status: 401 });

  const [usageRes, detailedRes] = await Promise.all([
    proxyGet("/v1/usage/current", ctx),
    proxyGet("/v1/usage/detailed", ctx),
  ]);

  return NextResponse.json({
    usage: usageRes.body,
    detailed: detailedRes.body,
    org: {
      org_id: ctx.orgId,
      org_name: ctx.orgName,
      plan: ctx.plan,
    },
  });
}
