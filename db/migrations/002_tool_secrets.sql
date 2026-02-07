-- ============================================================================
-- Foundry Database Schema
-- Migration 002: Tool secrets — user-provided credentials per tool + org
-- ============================================================================

-- Stores encrypted third-party credentials (API keys, tokens, user IDs)
-- scoped to a specific tool and organization. Injected as env vars at runtime.

CREATE TABLE IF NOT EXISTS tool_secrets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id VARCHAR(255) NOT NULL,        -- e.g., "tool-06052bf749b3"
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Secret data
    key VARCHAR(255) NOT NULL,            -- env var name, e.g., "TIKTOK_ACCESS_TOKEN"
    encrypted_value TEXT NOT NULL,         -- AES-encrypted value
    
    -- Metadata
    description VARCHAR(500),             -- optional label, e.g., "TikTok API token"
    service VARCHAR(100),                 -- optional grouping, e.g., "tiktok", "stripe"
    
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- One secret per key per tool per org
    UNIQUE(tool_id, org_id, key)
);

CREATE INDEX idx_tool_secrets_tool_org ON tool_secrets(tool_id, org_id);
CREATE INDEX idx_tool_secrets_org ON tool_secrets(org_id);

-- Trigger for updated_at
CREATE TRIGGER update_tool_secrets_updated_at BEFORE UPDATE ON tool_secrets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
