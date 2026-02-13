'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, useCallback } from 'react';
import Link from 'next/link';
import {
  getStoredApiKey,
  getStoredOrg,
  clearAuth,
  isAuthenticated,
  getUsage,
  getDetailedUsage,
  listKeys,
  createKey,
  revokeKey,
  listTools,
  ApiError,
  API_URL,
  type UsageStats,
  type UsageEvent,
  type KeyInfo,
  type CreateKeyResponse,
  type ToolManifest,
} from '@/lib/api';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Data
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [recentEvents, setRecentEvents] = useState<UsageEvent[]>([]);
  const [estimatedCost, setEstimatedCost] = useState(0);
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [tools, setTools] = useState<ToolManifest[]>([]);

  // Key creation
  const [newKeyName, setNewKeyName] = useState('');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<CreateKeyResponse | null>(null);
  const [creatingKey, setCreatingKey] = useState(false);
  const [copied, setCopied] = useState(false);

  // Active tab
  const [tab, setTab] = useState<'overview' | 'keys' | 'tools' | 'activity'>('overview');

  // ------------------------------------------
  // Initial load
  // ------------------------------------------
  const loadAll = useCallback(async () => {
    try {
      setError(null);
      const [usageRes, detailedRes, keysRes, toolsRes] = await Promise.allSettled([
        getUsage(),
        getDetailedUsage(),
        listKeys(),
        listTools(),
      ]);

      if (usageRes.status === 'fulfilled') setUsage(usageRes.value);
      if (detailedRes.status === 'fulfilled') {
        setRecentEvents(detailedRes.value.recent_events);
        setEstimatedCost(detailedRes.value.estimated_cost_usd);
      }
      if (keysRes.status === 'fulfilled') setKeys(keysRes.value);
      if (toolsRes.status === 'fulfilled') setTools(toolsRes.value);

      // If usage failed with 401, the key is invalid
      if (usageRes.status === 'rejected') {
        const err = usageRes.reason;
        if (err instanceof ApiError && err.status === 401) {
          clearAuth();
          router.push('/login');
          return;
        }
        setError(err.message || 'Failed to load usage data');
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Unknown error';
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (!isAuthenticated()) {
      router.push('/login');
      return;
    }
    loadAll();
  }, [router, loadAll]);

  // ------------------------------------------
  // Handlers
  // ------------------------------------------
  const handleCreateKey = async () => {
    setCreatingKey(true);
    try {
      const result = await createKey(newKeyName.trim() || 'Default');
      setNewlyCreatedKey(result);
      setNewKeyName('');
      // Refresh keys list
      const updatedKeys = await listKeys();
      setKeys(updatedKeys);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to create key';
      setError(msg);
    } finally {
      setCreatingKey(false);
    }
  };

  const handleRevokeKey = async (keyId: string) => {
    try {
      await revokeKey(keyId);
      setKeys((prev) => prev.filter((k) => k.key_id !== keyId));
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Failed to revoke key';
      setError(msg);
    }
  };

  const handleSignOut = () => {
    clearAuth();
    router.push('/');
  };

  const handleCopyKey = (key: string) => {
    navigator.clipboard.writeText(key);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ------------------------------------------
  // Loading
  // ------------------------------------------
  if (loading) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-white/20 border-t-white/80 rounded-full animate-spin" />
          <span className="text-white/50">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const org = getStoredOrg();
  const planLabel = usage?.plan || org?.plan || 'free';

  return (
    <div className="min-h-screen bg-[#030712] text-white">
      {/* Header */}
      <header className="border-b border-white/[0.06] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <Link
            href="/"
            className="text-2xl text-white"
            style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
          >
            Foundry
          </Link>
          <span className="text-white/20">|</span>
          <span className="text-white/40 text-sm">Dashboard</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden sm:inline text-white/40 text-xs font-mono">
            {getStoredApiKey()?.slice(0, 12)}...
          </span>
          <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-white/[0.06] border border-white/[0.08] text-white/50">
            {planLabel}
          </span>
          <button
            onClick={handleSignOut}
            className="text-sm text-white/40 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Error banner */}
        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)} className="text-red-400/60 hover:text-red-400">
              Dismiss
            </button>
          </div>
        )}

        {/* New key banner */}
        {newlyCreatedKey && (
          <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20">
            <p className="text-green-400 text-sm font-medium mb-2">
              New API key created. Copy it now — you will not see it again.
            </p>
            <div className="flex items-stretch gap-2">
              <code className="flex-1 bg-black/40 border border-white/[0.08] px-3 py-2 text-sm font-mono text-green-300 break-all select-all">
                {newlyCreatedKey.key}
              </code>
              <button
                onClick={() => handleCopyKey(newlyCreatedKey.key)}
                className="px-4 bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30 transition-colors shrink-0"
              >
                {copied ? 'Copied' : 'Copy'}
              </button>
              <button
                onClick={() => setNewlyCreatedKey(null)}
                className="px-3 text-white/40 text-sm hover:text-white transition-colors"
              >
                Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-8 border-b border-white/[0.06]">
          {(['overview', 'keys', 'tools', 'activity'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium capitalize transition-colors border-b-2 -mb-px ${
                tab === t
                  ? 'text-white border-white'
                  : 'text-white/40 border-transparent hover:text-white/60'
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {tab === 'overview' && (
          <OverviewTab
            usage={usage}
            tools={tools}
            keys={keys}
            estimatedCost={estimatedCost}
          />
        )}

        {tab === 'keys' && (
          <KeysTab
            keys={keys}
            newKeyName={newKeyName}
            setNewKeyName={setNewKeyName}
            creatingKey={creatingKey}
            onCreateKey={handleCreateKey}
            onRevokeKey={handleRevokeKey}
          />
        )}

        {tab === 'tools' && <ToolsTab tools={tools} />}

        {tab === 'activity' && <ActivityTab events={recentEvents} />}

        {/* Quick start */}
        <div className="mt-12">
          <h2
            className="text-2xl mb-4"
            style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
          >
            Quick Start
          </h2>
          <div className="bg-white/[0.03] border border-white/[0.08] p-6">
            <p className="text-white/60 mb-4 text-sm">
              Install the SDK and start building tools:
            </p>
            <pre className="bg-black/40 border border-white/[0.06] p-4 text-sm font-mono text-green-300 overflow-x-auto">
{`pip install foundry-sdk

from foundry import Foundry

client = Foundry(api_key="your-api-key")

# Create a tool from a description
tool = client.create("Calculate compound interest")
result = tool.invoke(principal=1000, rate=0.05, time=10)
print(result.result)`}
            </pre>
            <p className="text-white/30 text-xs mt-3">
              Base URL: <code className="text-white/50">{API_URL}</code>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

function OverviewTab({
  usage,
  tools,
  keys,
  estimatedCost,
}: {
  usage: UsageStats | null;
  tools: ToolManifest[];
  keys: KeyInfo[];
  estimatedCost: number;
}) {
  if (!usage) {
    return <p className="text-white/40">No usage data available.</p>;
  }

  return (
    <div>
      {/* Usage cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <UsageCard
          label="Tool Builds"
          current={usage.builds}
          limit={usage.builds_limit}
          color="pink"
        />
        <UsageCard
          label="Invocations"
          current={usage.invocations}
          limit={usage.invocations_limit}
          color="orange"
        />
        <UsageCard
          label="Searches"
          current={usage.searches}
          limit={usage.searches_limit}
          color="green"
        />
        <StatCard label="Est. Cost" value={`$${estimatedCost.toFixed(2)}`} sub="this month" />
      </div>

      {/* Summary row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <StatCard label="Active Tools" value={String(tools.filter((t) => t.status === 'ready').length)} sub={`${tools.length} total`} />
        <StatCard label="API Keys" value={String(keys.filter((k) => k.is_active).length)} sub="active" />
        <StatCard
          label="Plan"
          value={usage.plan.charAt(0).toUpperCase() + usage.plan.slice(1)}
          sub={
            usage.plan === 'free'
              ? 'Upgrade for higher limits'
              : usage.plan === 'pro'
                ? '$49/month'
                : '$199/month'
          }
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Keys Tab
// ---------------------------------------------------------------------------

function KeysTab({
  keys,
  newKeyName,
  setNewKeyName,
  creatingKey,
  onCreateKey,
  onRevokeKey,
}: {
  keys: KeyInfo[];
  newKeyName: string;
  setNewKeyName: (v: string) => void;
  creatingKey: boolean;
  onCreateKey: () => void;
  onRevokeKey: (id: string) => void;
}) {
  return (
    <div>
      <h2
        className="text-2xl mb-4"
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
      >
        API Keys
      </h2>

      {/* Create key */}
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={newKeyName}
          onChange={(e) => setNewKeyName(e.target.value)}
          placeholder="Key name (e.g., Production)"
          className="bg-white/[0.05] border border-white/[0.08] px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-white/20 flex-1 text-sm"
          onKeyDown={(e) => e.key === 'Enter' && onCreateKey()}
        />
        <button
          onClick={onCreateKey}
          disabled={creatingKey}
          className="bg-white text-black px-6 py-2.5 font-medium text-sm hover:bg-white/90 transition-colors disabled:opacity-50 shrink-0"
        >
          {creatingKey ? 'Creating...' : 'Create Key'}
        </button>
      </div>

      {/* Keys table */}
      <div className="border border-white/[0.08] overflow-hidden">
        <div className="grid grid-cols-5 gap-4 px-4 py-3 bg-white/[0.03] border-b border-white/[0.08] text-xs text-white/40 uppercase tracking-wider">
          <div>Name</div>
          <div>Prefix</div>
          <div>Created</div>
          <div>Last Used</div>
          <div className="text-right">Actions</div>
        </div>

        {keys.length === 0 ? (
          <div className="px-4 py-10 text-center text-white/30 text-sm">
            No API keys yet. Create one to get started.
          </div>
        ) : (
          keys.map((key) => (
            <div
              key={key.key_id}
              className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.04] text-sm items-center"
            >
              <div className="text-white">{key.name}</div>
              <div className="text-white/50 font-mono text-xs">{key.prefix}...</div>
              <div className="text-white/40 text-xs">
                {new Date(key.created_at).toLocaleDateString()}
              </div>
              <div className="text-white/40 text-xs">
                {key.last_used_at
                  ? new Date(key.last_used_at).toLocaleDateString()
                  : 'Never'}
              </div>
              <div className="text-right">
                <button
                  onClick={() => onRevokeKey(key.key_id)}
                  className="text-xs text-red-400/60 hover:text-red-400 transition-colors"
                >
                  Revoke
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tools Tab
// ---------------------------------------------------------------------------

function ToolsTab({ tools }: { tools: ToolManifest[] }) {
  if (tools.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-white/40 mb-2">No tools created yet.</p>
        <p className="text-white/30 text-sm">
          Use the API or SDK to create your first tool.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2
        className="text-2xl mb-4"
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
      >
        Tools
      </h2>

      <div className="space-y-3">
        {tools.map((tool) => (
          <div
            key={tool.tool_id}
            className="bg-white/[0.03] border border-white/[0.08] p-5"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <h3 className="text-white font-medium">{tool.name}</h3>
                <p className="text-white/40 text-sm mt-0.5">{tool.description}</p>
              </div>
              <span
                className={`px-2 py-0.5 text-[10px] uppercase tracking-wider border ${
                  tool.status === 'ready'
                    ? 'text-green-400 border-green-500/20 bg-green-500/10'
                    : tool.status === 'expired'
                      ? 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10'
                      : 'text-red-400 border-red-500/20 bg-red-500/10'
                }`}
              >
                {tool.status}
              </span>
            </div>
            <div className="flex items-center gap-4 mt-3 text-xs text-white/30">
              <span className="font-mono">{tool.tool_id}</span>
              <span>Created {new Date(tool.created_at).toLocaleDateString()}</span>
              {tool.expires_at && (
                <span>Expires {new Date(tool.expires_at).toLocaleDateString()}</span>
              )}
            </div>
            <div className="mt-3">
              <code className="text-xs text-white/40 font-mono bg-black/20 px-2 py-1 border border-white/[0.04]">
                POST {tool.invoke_url}
              </code>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Activity Tab
// ---------------------------------------------------------------------------

function ActivityTab({ events }: { events: UsageEvent[] }) {
  const typeLabels: Record<string, string> = {
    tool_build: 'Build',
    tool_invoke: 'Invoke',
    search: 'Search',
  };

  const typeColors: Record<string, string> = {
    tool_build: 'text-pink-400',
    tool_invoke: 'text-orange-400',
    search: 'text-green-400',
  };

  if (events.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-white/40 mb-2">No activity yet.</p>
        <p className="text-white/30 text-sm">
          API calls will show up here as you use Foundry.
        </p>
      </div>
    );
  }

  return (
    <div>
      <h2
        className="text-2xl mb-4"
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
      >
        Recent Activity
      </h2>

      <div className="border border-white/[0.08] overflow-hidden">
        <div className="grid grid-cols-5 gap-4 px-4 py-3 bg-white/[0.03] border-b border-white/[0.08] text-xs text-white/40 uppercase tracking-wider">
          <div>Type</div>
          <div>Tool</div>
          <div>Duration</div>
          <div>Tokens</div>
          <div>Time</div>
        </div>

        {events.map((event, i) => (
          <div
            key={i}
            className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.04] text-sm items-center"
          >
            <div className={typeColors[event.event_type] || 'text-white/50'}>
              {typeLabels[event.event_type] || event.event_type}
            </div>
            <div className="text-white/40 font-mono text-xs truncate">
              {event.tool_id || '—'}
            </div>
            <div className="text-white/40 text-xs">
              {event.execution_time_ms > 0 ? `${event.execution_time_ms}ms` : '—'}
            </div>
            <div className="text-white/40 text-xs">
              {event.tokens_used > 0 ? event.tokens_used.toLocaleString() : '—'}
            </div>
            <div className="text-white/30 text-xs">
              {new Date(event.created_at).toLocaleString()}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared components
// ---------------------------------------------------------------------------

function UsageCard({
  label,
  current,
  limit,
  color,
}: {
  label: string;
  current: number;
  limit: number;
  color: 'pink' | 'orange' | 'green';
}) {
  const pct = limit > 0 ? (current / limit) * 100 : 0;
  const colorMap = {
    pink: { bar: 'bg-pink-500', text: 'text-pink-400' },
    orange: { bar: 'bg-orange-500', text: 'text-orange-400' },
    green: { bar: 'bg-green-500', text: 'text-green-400' },
  };
  const c = colorMap[color];

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] p-5">
      <div className="flex items-center justify-between mb-2">
        <span className="text-white/40 text-xs uppercase tracking-wider">{label}</span>
        <span className={`text-[10px] ${c.text}`}>{pct.toFixed(0)}%</span>
      </div>
      <div
        className="text-3xl mb-3"
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
      >
        {current.toLocaleString()}
        <span className="text-white/20 text-lg"> / {limit.toLocaleString()}</span>
      </div>
      <div className="w-full h-1 bg-white/[0.05] rounded-full overflow-hidden">
        <div
          className={`h-full ${c.bar} transition-all duration-500`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
}: {
  label: string;
  value: string;
  sub: string;
}) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.08] p-5">
      <span className="text-white/40 text-xs uppercase tracking-wider">{label}</span>
      <div
        className="text-2xl mt-1"
        style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
      >
        {value}
      </div>
      <span className="text-white/30 text-xs">{sub}</span>
    </div>
  );
}
