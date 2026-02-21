-- Migration 003: Better Auth Integration
-- Run this before deploying Better Auth.
-- Better Auth will create its own tables (user, session, account, verification)
-- via `npx @better-auth/cli migrate`. This migration adjusts existing tables.

-- 1. Make api_keys.created_by nullable
--    (existing keys pre-BA have no user; BA will set it for new keys)
ALTER TABLE api_keys ALTER COLUMN created_by DROP NOT NULL;

-- 2. Add owner linkage columns to organizations
--    Better Auth uses text IDs (CUID), not UUIDs
ALTER TABLE organizations
  ADD COLUMN IF NOT EXISTS owner_user_id TEXT,
  ADD COLUMN IF NOT EXISTS owner_email TEXT;

CREATE INDEX IF NOT EXISTS idx_organizations_owner_user
  ON organizations(owner_user_id);

CREATE INDEX IF NOT EXISTS idx_organizations_owner_email
  ON organizations(owner_email);

-- 3. Update org_members to use TEXT user_id
--    (Better Auth IDs are text, not UUID; table is currently empty/unused)
ALTER TABLE org_members
  ALTER COLUMN user_id TYPE TEXT USING user_id::text;

ALTER TABLE org_members
  ALTER COLUMN invited_by TYPE TEXT USING invited_by::text;
