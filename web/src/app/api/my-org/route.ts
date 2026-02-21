import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { headers } from "next/headers";
import { Pool } from "pg";

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false },
  max: 5,
});

export async function GET() {
  const session = await auth.api.getSession({ headers: await headers() });
  if (!session) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const client = await pool.connect();
  try {
    const orgRow = await client.query(
      `SELECT id, name, plan, owner_email
       FROM organizations
       WHERE owner_user_id = $1
       LIMIT 1`,
      [session.user.id],
    );

    if (!orgRow.rows[0]) {
      return NextResponse.json({ error: "No organization found" }, { status: 404 });
    }

    const org = orgRow.rows[0];

    // Get the oldest active key prefix (for display only — never return full key)
    const keyRow = await client.query(
      `SELECT key_prefix
       FROM api_keys
       WHERE org_id = $1 AND is_active = TRUE AND revoked_at IS NULL
       ORDER BY created_at ASC
       LIMIT 1`,
      [org.id],
    );

    return NextResponse.json({
      org_id: org.id,
      org_name: org.name,
      plan: org.plan,
      email: session.user.email,
      key_prefix: keyRow.rows[0]?.key_prefix ?? null,
    });
  } finally {
    client.release();
  }
}
