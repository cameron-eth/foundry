/**
 * Foundry API client.
 *
 * After Better Auth migration:
 * - Session/identity is managed by Better Auth (cookie-based)
 * - `fnd_...` API keys are used for FastAPI (SDK/programmatic access)
 * - Keys stored in memory + localStorage for SDK/programmatic use
 */

export const API_URL =
  process.env.NEXT_PUBLIC_FOUNDRY_API_URL ||
  "https://camfleety--toolfoundry-serve.modal.run";

// ---------------------------------------------------------------------------
// In-memory active API key (set after creating a key in the dashboard)
// ---------------------------------------------------------------------------

let _activeApiKey: string | null = null;

export function setActiveApiKey(key: string) {
  _activeApiKey = key;
  if (typeof window !== "undefined") {
    localStorage.setItem("foundry_api_key", key);
  }
}

export function getActiveApiKey(): string | null {
  if (_activeApiKey) return _activeApiKey;
  if (typeof window !== "undefined") {
    const stored = localStorage.getItem("foundry_api_key");
    if (stored) {
      _activeApiKey = stored;
      return stored;
    }
  }
  return null;
}

// ---------------------------------------------------------------------------
// Key storage
// ---------------------------------------------------------------------------

const STORAGE_KEY = "foundry_api_key";
const ORG_KEY = "foundry_org";

export interface StoredOrg {
  org_id: string;
  org_name: string;
  plan: string;
}

export function getStoredApiKey(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(STORAGE_KEY);
}

export function setStoredApiKey(key: string) {
  localStorage.setItem(STORAGE_KEY, key);
}

export function getStoredOrg(): StoredOrg | null {
  if (typeof window === "undefined") return null;
  const raw = localStorage.getItem(ORG_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
}

export function setStoredOrg(org: StoredOrg) {
  localStorage.setItem(ORG_KEY, JSON.stringify(org));
}

export function clearAuth() {
  localStorage.removeItem(STORAGE_KEY);
  localStorage.removeItem(ORG_KEY);
}

export function isAuthenticated(): boolean {
  return !!getStoredApiKey();
}

// ---------------------------------------------------------------------------
// Fetch helper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
  overrideKey?: string | null,
): Promise<T> {
  // Use override key if provided, otherwise fall back to active key
  const apiKey = overrideKey !== undefined ? overrideKey : getActiveApiKey();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail || JSON.stringify(body));
  }

  return res.json();
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface RegisterRequest {
  org_name: string;
  email?: string;
  plan?: string;
}

export interface RegisterResponse {
  org_id: string;
  org_name: string;
  api_key: string;
  key_prefix: string;
  plan: string;
  message: string;
}

export interface UsageStats {
  builds: number;
  invocations: number;
  searches: number;
  builds_limit: number;
  invocations_limit: number;
  searches_limit: number;
  plan: string;
}

export interface UsageEvent {
  event_type: string;
  tool_id: string | null;
  execution_time_ms: number;
  tokens_used: number;
  created_at: string;
}

export interface DetailedUsage {
  stats: UsageStats;
  recent_events: UsageEvent[];
  estimated_cost_usd: number;
}

export interface KeyInfo {
  key_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

export interface CreateKeyResponse {
  key: string;
  key_id: string;
  prefix: string;
  name: string;
}

export interface ToolManifest {
  tool_id: string;
  name: string;
  description: string;
  status: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown> | null;
  invoke_url: string;
  created_at: string;
  expires_at: string | null;
}

// ---------------------------------------------------------------------------
// API methods
// ---------------------------------------------------------------------------

/** Register a new organization (no auth required — SDK/headless path). */
export async function register(
  req: RegisterRequest,
): Promise<RegisterResponse> {
  return apiFetch<RegisterResponse>("/v1/keys/register", {
    method: "POST",
    body: JSON.stringify(req),
  }, null); // explicitly no API key
}

/** Get current-month usage stats. */
export async function getUsage(): Promise<UsageStats> {
  return apiFetch<UsageStats>("/v1/usage/current");
}

/** Get usage stats — for dashboard (uses active key or provided key). */
export async function getUsageWithKey(key?: string | null): Promise<UsageStats> {
  return apiFetch<UsageStats>("/v1/usage/current", {}, key ?? getActiveApiKey());
}

/** Get detailed usage with recent events. */
export async function getDetailedUsage(): Promise<DetailedUsage> {
  return apiFetch<DetailedUsage>("/v1/usage/detailed");
}

/** Get detailed usage — for dashboard. */
export async function getDetailedUsageWithKey(key?: string | null): Promise<DetailedUsage> {
  return apiFetch<DetailedUsage>("/v1/usage/detailed", {}, key ?? getActiveApiKey());
}

/** List API keys for the authenticated org. */
export async function listKeys(): Promise<KeyInfo[]> {
  const res = await apiFetch<{ keys: KeyInfo[] }>("/v1/keys/list");
  return res.keys;
}

/** Create a new API key. */
export async function createKey(name: string): Promise<CreateKeyResponse> {
  return apiFetch<CreateKeyResponse>("/v1/keys/create", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

/** Revoke an API key. */
export async function revokeKey(
  keyId: string,
): Promise<{ message: string }> {
  return apiFetch<{ message: string }>(`/v1/keys/${keyId}/revoke`, {
    method: "POST",
  });
}

/** List tools for the authenticated org. */
export async function listTools(): Promise<ToolManifest[]> {
  const res = await apiFetch<{ tools: ToolManifest[] }>("/v1/tools");
  return res.tools;
}

/** Health check (no auth). */
export async function healthCheck(): Promise<{ status: string }> {
  return apiFetch<{ status: string }>("/health");
}

// ---------------------------------------------------------------------------
// Billing
// ---------------------------------------------------------------------------

export interface CheckoutResponse {
  checkout_url: string | null;
  message: string;
  error: string | null;
}

export interface EntitlementResponse {
  allowed: boolean;
  feature_id: string;
  balance: number | null;
  usage: number | null;
  included_usage: number | null;
  unlimited: boolean;
}

export interface BillingStatus {
  org_id: string;
  autumn_enabled: boolean;
  features: Record<
    string,
    {
      allowed: boolean;
      balance: number | null;
      usage: number | null;
      included_usage: number | null;
      unlimited: boolean;
    }
  >;
}

/** Create a Stripe checkout URL for a plan upgrade. */
export async function createCheckout(
  productId: string,
  successUrl?: string,
  cancelUrl?: string,
): Promise<CheckoutResponse> {
  return apiFetch<CheckoutResponse>("/v1/billing/checkout", {
    method: "POST",
    body: JSON.stringify({
      product_id: productId,
      success_url: successUrl || `${window.location.origin}/dashboard?upgraded=1`,
      cancel_url: cancelUrl || `${window.location.origin}/pricing`,
    }),
  });
}

/** Check if the org can use a specific feature. */
export async function checkEntitlement(
  featureId: string,
): Promise<EntitlementResponse> {
  return apiFetch<EntitlementResponse>("/v1/billing/check", {
    method: "POST",
    body: JSON.stringify({ feature_id: featureId }),
  });
}

/** Get full billing status with all feature balances. */
export async function getBillingStatus(): Promise<BillingStatus> {
  return apiFetch<BillingStatus>("/v1/billing/status");
}

// API_URL is already exported above at declaration
