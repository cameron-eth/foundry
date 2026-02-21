import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { Pool } from "pg";
import { generateApiKey } from "@/lib/api-key-utils";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  max: 5,
});

const AUTUMN_SECRET_KEY = process.env.AUTUMN_SECRET_KEY ?? "";
const AUTUMN_URL = "https://api.useautumn.com";

async function setupAutumnCustomer(
  orgId: string,
  name: string,
  email: string | null,
  plan: string,
) {
  if (!AUTUMN_SECRET_KEY) return;

  try {
    await fetch(`${AUTUMN_URL}/v1/customers`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${AUTUMN_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ id: orgId, name, email }),
    });

    const productMap: Record<string, string> = { paygo: "paygo", pro: "pro" };
    await fetch(`${AUTUMN_URL}/v1/attach`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${AUTUMN_SECRET_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        customer_id: orgId,
        product_id: productMap[plan] ?? "paygo",
      }),
    });
  } catch (err) {
    // Non-blocking — log but don't fail signup
    console.error("Autumn setup error (non-blocking):", err);
  }
}

export async function POST(req: NextRequest) {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  let body: { orgName?: string; plan?: string };
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ error: "Invalid JSON" }, { status: 400 });
  }

  const { orgName, plan = "paygo" } = body;

  if (!orgName || orgName.trim().length === 0) {
    return NextResponse.json(
      { error: "Organization name is required" },
      { status: 400 },
    );
  }

  const validPlans = ["paygo", "pro"];
  if (!validPlans.includes(plan)) {
    return NextResponse.json(
      { error: `Invalid plan. Choose from: ${validPlans.join(", ")}` },
      { status: 400 },
    );
  }

  const userId = session.user.id;
  const userEmail = session.user.email;
  const slug = orgName
    .toLowerCase()
    .trim()
    .replace(/\s+/g, "-")
    .replace(/[^a-z0-9-]/g, "")
    .slice(0, 50);

  const client = await pool.connect();
  try {
    // Check slug uniqueness
    const existing = await client.query(
      "SELECT id FROM organizations WHERE slug = $1",
      [slug],
    );
    if (existing.rows.length > 0) {
      return NextResponse.json(
        {
          error:
            "Organization name already taken. Please choose a different name.",
        },
        { status: 409 },
      );
    }

    // Check user doesn't already have an org
    const existingOrg = await client.query(
      "SELECT id FROM organizations WHERE owner_user_id = $1",
      [userId],
    );
    if (existingOrg.rows.length > 0) {
      return NextResponse.json(
        { error: "You already have an organization" },
        { status: 409 },
      );
    }

    // Look up plan limits
    const planRow = await client.query(
      `SELECT monthly_builds, monthly_invocations, monthly_searches, concurrent_tools
       FROM billing_plans WHERE id = $1`,
      [plan],
    );
    if (!planRow.rows[0]) {
      return NextResponse.json(
        { error: "Plan configuration not found" },
        { status: 500 },
      );
    }
    const p = planRow.rows[0];

    const orgId = crypto.randomUUID();

    // Create organization
    await client.query(
      `INSERT INTO organizations (
        id, name, slug, plan,
        monthly_build_limit, monthly_invoke_limit,
        monthly_search_limit, concurrent_tools_limit,
        owner_user_id, owner_email
      ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
      [
        orgId,
        orgName.trim(),
        slug,
        plan,
        p.monthly_builds,
        p.monthly_invocations,
        p.monthly_searches,
        p.concurrent_tools,
        userId,
        userEmail,
      ],
    );

    // Note: org_members.user_id is still UUID type in the DB schema.
    // We link via organizations.owner_user_id (TEXT) instead.
    // org_members will be migrated to TEXT in a follow-up migration.

    // Generate first API key
    const { fullKey, prefix, keyHash } = generateApiKey();
    await client.query(
      `INSERT INTO api_keys (org_id, created_by, name, key_prefix, key_hash, scopes)
       VALUES ($1, $2, $3, $4, $5, ARRAY['tools:create','tools:invoke','tools:read','search'])`,
      [orgId, userId, "Default Key", prefix, keyHash],
    );

    // Setup Autumn billing (async, non-blocking)
    setupAutumnCustomer(orgId, orgName.trim(), userEmail, plan).catch(
      console.error,
    );

    return NextResponse.json({
      org_id: orgId,
      org_name: orgName.trim(),
      api_key: fullKey, // shown once
      key_prefix: prefix,
      plan,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("setup-org error:", msg);
    return NextResponse.json(
      { error: "Failed to create organization", detail: msg },
      { status: 500 },
    );
  } finally {
    client.release();
  }
}
