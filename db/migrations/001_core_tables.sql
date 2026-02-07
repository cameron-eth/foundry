-- ============================================================================
-- Foundry Core Database Schema
-- Migration 001: Core tables for auth, orgs, API keys, tools, and usage
-- ============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- ORGANIZATIONS
-- ============================================================================

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255) UNIQUE NOT NULL,
    
    -- Plan & billing
    plan VARCHAR(50) NOT NULL DEFAULT 'free',  -- free, pro, scale, enterprise
    stripe_customer_id VARCHAR(255),
    stripe_subscription_id VARCHAR(255),
    
    -- Limits (overridable per-org)
    monthly_build_limit INT NOT NULL DEFAULT 100,     -- tools per month
    monthly_invoke_limit INT NOT NULL DEFAULT 1000,   -- invocations per month
    monthly_search_limit INT NOT NULL DEFAULT 500,    -- searches per month
    concurrent_tools_limit INT NOT NULL DEFAULT 10,   -- active tools at once
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
CREATE INDEX idx_organizations_stripe ON organizations(stripe_customer_id);


-- ============================================================================
-- ORGANIZATION MEMBERS (links Neon Auth users to orgs)
-- ============================================================================

CREATE TABLE IF NOT EXISTS org_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,  -- References neon_auth.users.id
    
    role VARCHAR(50) NOT NULL DEFAULT 'member',  -- owner, admin, member, viewer
    
    invited_by UUID,  -- user_id of inviter
    joined_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(org_id, user_id)
);

CREATE INDEX idx_org_members_user ON org_members(user_id);
CREATE INDEX idx_org_members_org ON org_members(org_id);


-- ============================================================================
-- API KEYS
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID NOT NULL,  -- user_id who created the key
    
    -- Key data
    name VARCHAR(255) NOT NULL DEFAULT 'Default',
    key_prefix VARCHAR(12) NOT NULL,  -- First 8 chars for identification (e.g., "fnd_abc1")
    key_hash VARCHAR(255) NOT NULL,    -- SHA-256 hash of the full key
    
    -- Permissions
    scopes TEXT[] NOT NULL DEFAULT ARRAY['tools:create', 'tools:invoke', 'tools:read', 'search'],
    
    -- Rate limits (per-key overrides, NULL = use org limits)
    rate_limit_rpm INT,  -- requests per minute
    
    -- Status
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    last_used_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX idx_api_keys_org ON api_keys(org_id);


-- ============================================================================
-- TOOLS (persistent storage - replaces in-memory/modal dict)
-- ============================================================================

CREATE TABLE IF NOT EXISTS tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id VARCHAR(255) UNIQUE NOT NULL,  -- e.g., "tool-5150f7c16f8c"
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_by UUID,  -- user_id
    
    -- Tool metadata
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'building',  -- building, ready, failed, expired, deprecated
    
    -- Schemas
    input_schema JSONB NOT NULL DEFAULT '{}',
    output_schema JSONB NOT NULL DEFAULT '{"type": "object"}',
    
    -- Implementation
    implementation TEXT,
    sandbox_id VARCHAR(255),
    error_message TEXT,
    
    -- Context
    conversation_id VARCHAR(255),
    capability_description TEXT,
    
    -- Lifecycle
    ttl_hours INT NOT NULL DEFAULT 24,
    build_duration_ms INT,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    deprecated_at TIMESTAMPTZ
);

CREATE INDEX idx_tools_tool_id ON tools(tool_id);
CREATE INDEX idx_tools_org ON tools(org_id);
CREATE INDEX idx_tools_status ON tools(status);
CREATE INDEX idx_tools_expires ON tools(expires_at) WHERE expires_at IS NOT NULL;


-- ============================================================================
-- USAGE EVENTS (every billable action)
-- ============================================================================

CREATE TABLE IF NOT EXISTS usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id UUID,          -- NULL for API key access
    api_key_id UUID REFERENCES api_keys(id),
    
    -- Event details
    event_type VARCHAR(50) NOT NULL,  -- 'tool_build', 'tool_invoke', 'search', 'tool_rebuild'
    tool_id VARCHAR(255),
    
    -- Metering
    tokens_used INT DEFAULT 0,         -- LLM tokens consumed
    execution_time_ms INT DEFAULT 0,
    compute_units DECIMAL(10,4) DEFAULT 0,  -- Normalized compute units for billing
    
    -- Request metadata
    request_id VARCHAR(255),
    endpoint VARCHAR(255),
    status_code INT,
    error TEXT,
    
    -- Cost tracking
    estimated_cost_usd DECIMAL(10,6) DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'
);

-- Partition-friendly indexes for time-series queries
CREATE INDEX idx_usage_events_org_time ON usage_events(org_id, created_at DESC);
CREATE INDEX idx_usage_events_type ON usage_events(event_type, created_at DESC);
CREATE INDEX idx_usage_events_api_key ON usage_events(api_key_id) WHERE api_key_id IS NOT NULL;


-- ============================================================================
-- BILLING PLANS
-- ============================================================================

CREATE TABLE IF NOT EXISTS billing_plans (
    id VARCHAR(50) PRIMARY KEY,  -- 'free', 'pro', 'scale', 'enterprise'
    name VARCHAR(255) NOT NULL,
    
    -- Pricing
    price_monthly_usd DECIMAL(10,2) NOT NULL DEFAULT 0,
    price_yearly_usd DECIMAL(10,2),
    
    -- Included limits
    monthly_builds INT NOT NULL DEFAULT 100,
    monthly_invocations INT NOT NULL DEFAULT 1000,
    monthly_searches INT NOT NULL DEFAULT 500,
    concurrent_tools INT NOT NULL DEFAULT 10,
    max_ttl_hours INT NOT NULL DEFAULT 24,
    
    -- Overage pricing (per unit above limit)
    overage_build_usd DECIMAL(10,4) DEFAULT 0.10,
    overage_invoke_usd DECIMAL(10,4) DEFAULT 0.01,
    overage_search_usd DECIMAL(10,4) DEFAULT 0.005,
    
    -- Features
    features JSONB NOT NULL DEFAULT '{}',
    
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ============================================================================
-- MONTHLY USAGE SUMMARY (materialized for fast lookups)
-- ============================================================================

CREATE TABLE IF NOT EXISTS monthly_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    
    -- Period
    period_start DATE NOT NULL,  -- First day of month
    period_end DATE NOT NULL,    -- Last day of month
    
    -- Counts
    builds_count INT NOT NULL DEFAULT 0,
    invocations_count INT NOT NULL DEFAULT 0,
    searches_count INT NOT NULL DEFAULT 0,
    
    -- Cost
    total_tokens INT NOT NULL DEFAULT 0,
    total_compute_units DECIMAL(10,4) NOT NULL DEFAULT 0,
    estimated_cost_usd DECIMAL(10,4) NOT NULL DEFAULT 0,
    
    -- Billing
    included_cost_usd DECIMAL(10,4) NOT NULL DEFAULT 0,
    overage_cost_usd DECIMAL(10,4) NOT NULL DEFAULT 0,
    
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    UNIQUE(org_id, period_start)
);

CREATE INDEX idx_monthly_usage_org ON monthly_usage(org_id, period_start DESC);


-- ============================================================================
-- SEED: Default billing plans
-- ============================================================================

INSERT INTO billing_plans (id, name, price_monthly_usd, monthly_builds, monthly_invocations, monthly_searches, concurrent_tools, max_ttl_hours, overage_build_usd, overage_invoke_usd, overage_search_usd, features)
VALUES
    ('free', 'Free', 0, 100, 1000, 500, 10, 24, 0.10, 0.01, 0.005, '{"polymarket": true, "exa_search": false, "priority_builds": false}'),
    ('pro', 'Pro', 49.00, 1000, 25000, 5000, 50, 168, 0.08, 0.005, 0.003, '{"polymarket": true, "exa_search": true, "priority_builds": true, "custom_domains": false}'),
    ('scale', 'Scale', 199.00, 10000, 250000, 50000, 200, 720, 0.05, 0.002, 0.001, '{"polymarket": true, "exa_search": true, "priority_builds": true, "custom_domains": true, "sla": true}'),
    ('enterprise', 'Enterprise', 0, -1, -1, -1, -1, -1, 0, 0, 0, '{"polymarket": true, "exa_search": true, "priority_builds": true, "custom_domains": true, "sla": true, "dedicated": true}')
ON CONFLICT (id) DO NOTHING;


-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to get current month usage for an org
CREATE OR REPLACE FUNCTION get_current_usage(p_org_id UUID)
RETURNS TABLE(builds INT, invocations INT, searches INT) AS $$
BEGIN
    RETURN QUERY
    SELECT
        COALESCE(SUM(CASE WHEN event_type = 'tool_build' THEN 1 ELSE 0 END), 0)::INT as builds,
        COALESCE(SUM(CASE WHEN event_type = 'tool_invoke' THEN 1 ELSE 0 END), 0)::INT as invocations,
        COALESCE(SUM(CASE WHEN event_type = 'search' THEN 1 ELSE 0 END), 0)::INT as searches
    FROM usage_events
    WHERE org_id = p_org_id
    AND created_at >= date_trunc('month', NOW())
    AND created_at < date_trunc('month', NOW()) + INTERVAL '1 month';
END;
$$ LANGUAGE plpgsql;


-- Function to check if org is within limits
CREATE OR REPLACE FUNCTION check_usage_limit(p_org_id UUID, p_event_type VARCHAR)
RETURNS BOOLEAN AS $$
DECLARE
    v_limit INT;
    v_current INT;
BEGIN
    -- Get the org's limit for this event type
    SELECT
        CASE p_event_type
            WHEN 'tool_build' THEN o.monthly_build_limit
            WHEN 'tool_invoke' THEN o.monthly_invoke_limit
            WHEN 'search' THEN o.monthly_search_limit
            ELSE 0
        END INTO v_limit
    FROM organizations o
    WHERE o.id = p_org_id;
    
    -- -1 means unlimited
    IF v_limit = -1 THEN
        RETURN TRUE;
    END IF;
    
    -- Count current month usage
    SELECT COUNT(*) INTO v_current
    FROM usage_events
    WHERE org_id = p_org_id
    AND event_type = p_event_type
    AND created_at >= date_trunc('month', NOW());
    
    RETURN v_current < v_limit;
END;
$$ LANGUAGE plpgsql;


-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_organizations_updated_at BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_tools_updated_at BEFORE UPDATE ON tools
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
