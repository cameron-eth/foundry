/**
 * Server-side helper: resolve the org and a working API key for the current BA session.
 * Used by Next.js route handlers to proxy calls to FastAPI on behalf of the logged-in user.
 */

import { auth } from "@/lib/auth";
import { Pool } from "pg";
import { headers } from "next/headers";
import crypto from "crypto";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  max: 5,
});

export interface OrgContext {
  userId: string;
  orgId: string;
  orgName: string;
  plan: string;
  apiKey: string; // full fnd_... key for proxying to FastAPI
}

/**
 * Get or create a short-lived server-side API key for the current session user.
 * Returns the full key so we can pass it as X-API-Key to FastAPI.
 *
 * Strategy: we keep one "Dashboard Key" per org in the DB.
 * On first call we generate it and store it (hashed). On subsequent calls
 * we can't recover it (hash only) — so we instead always generate a fresh key
 * and store it. This is safe because it's a server-side operation.
 *
 * Actually simpler: just pass the org_id and look up the key_hash to verify
 * the org exists, but we can't recover the raw key. Instead we generate a
 * new ephemeral key each request and immediately revoke it — too slow.
 *
 * Best approach: store one "server session key" per org that we CAN recover.
 * We encrypt it with the BETTER_AUTH_SECRET.
 */

const FOUNDRY_API_URL =
  process.env.NEXT_PUBLIC_FOUNDRY_API_URL ||
  "https://camfleety--toolfoundry-serve.modal.run";

/**
 * Resolve the current session's org context including a usable API key.
 * The key is generated fresh and stored (replacing any previous server key).
 */
export async function getOrgContext(): Promise<OrgContext | null> {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) return null;

  const client = await pool.connect();
  try {
    const orgRow = await client.query(
      `SELECT id, name, plan FROM organizations WHERE owner_user_id = $1 LIMIT 1`,
      [session.user.id]
    );
    if (!orgRow.rows[0]) return null;

    const org = orgRow.rows[0];

    // Generate a fresh API key and store it as "server-session-key"
    // (replacing the previous one — we always have at most one server key per org)
    const raw = crypto.randomBytes(32).toString("hex");
    const fullKey = `fnd_${raw}`;
    const prefix = fullKey.slice(0, 12);
    const keyHash = crypto.createHash("sha256").update(fullKey).digest("hex");

    // Upsert the server session key (revoke old one, insert new one)
    await client.query(
      `UPDATE api_keys SET revoked_at = NOW()
       WHERE org_id = $1 AND name = '__server_session__' AND revoked_at IS NULL`,
      [org.id]
    );
    await client.query(
      `INSERT INTO api_keys (org_id, created_by, name, key_prefix, key_hash, scopes)
       VALUES ($1, $2, '__server_session__', $3, $4,
               ARRAY['tools:create','tools:invoke','tools:read','search'])`,
      [org.id, session.user.id, prefix, keyHash]
    );

    return {
      userId: session.user.id,
      orgId: org.id,
      orgName: org.name,
      plan: org.plan,
      apiKey: fullKey,
    };
  } finally {
    client.release();
  }
}

/**
 * Proxy a GET request to FastAPI using the org's server session key.
 */
export async function proxyGet(path: string, ctx: OrgContext) {
  const res = await fetch(`${FOUNDRY_API_URL}${path}`, {
    headers: { "X-API-Key": ctx.apiKey },
  });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body };
}

/**
 * Proxy a POST request to FastAPI using the org's server session key.
 */
export async function proxyPost(
  path: string,
  ctx: OrgContext,
  data: unknown
) {
  const res = await fetch(`${FOUNDRY_API_URL}${path}`, {
    method: "POST",
    headers: {
      "X-API-Key": ctx.apiKey,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  });
  const body = await res.json().catch(() => ({}));
  return { status: res.status, body };
}

/**
 * Check if the org has an active Stripe subscription via Autumn.
 * Returns true if they have payment on file (any product active).
 */
export async function hasActiveSubscription(orgId: string): Promise<boolean> {
  const autumnKey = process.env.AUTUMN_SECRET_KEY;
  if (!autumnKey) return true; // If Autumn not configured, don't gate

  try {
    const res = await fetch(
      `https://api.useautumn.com/v1/customers/${orgId}`,
      {
        headers: { Authorization: `Bearer ${autumnKey}` },
      }
    );
    if (!res.ok) return false;
    const data = await res.json();
    // If they have any active products, they have payment on file
    return Array.isArray(data.products) && data.products.length > 0;
  } catch {
    return false;
  }
}

/**
 * Get a Stripe checkout URL for the given product.
 */
export async function getCheckoutUrl(
  orgId: string,
  orgName: string,
  email: string | null,
  productId: string,
  successUrl: string,
  cancelUrl: string
): Promise<string | null> {
  const autumnKey = process.env.AUTUMN_SECRET_KEY;
  if (!autumnKey) return null;

  const res = await fetch("https://api.useautumn.com/v1/attach", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${autumnKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      customer_id: orgId,
      product_id: productId,
      success_url: successUrl,
      cancel_url: cancelUrl,
    }),
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.checkout_url ?? null;
}

export { FOUNDRY_API_URL };
