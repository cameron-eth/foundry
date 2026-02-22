'use client';

import { useRouter } from 'next/navigation';
import { useEffect, useState, useCallback, useRef } from 'react';
import Link from 'next/link';
import { useSession, signOut } from '@/lib/auth-client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OrgData {
  org_id: string;
  org_name: string;
  plan: string;
}

interface UsageStats {
  builds: number;
  invocations: number;
  searches: number;
  builds_limit: number;
  invocations_limit: number;
  searches_limit: number;
  plan: string;
}

interface UsageEvent {
  event_type: string;
  tool_id: string | null;
  execution_time_ms: number;
  tokens_used: number;
  created_at: string;
}

interface KeyInfo {
  key_id: string;
  name: string;
  prefix: string;
  scopes: string[];
  is_active: boolean;
  created_at: string;
  last_used_at: string | null;
}

interface ToolManifest {
  tool_id: string;
  name: string;
  description: string;
  status: string;
  input_schema: Record<string, unknown>;
  invoke_url: string;
  created_at: string;
}

interface BillingInfo {
  has_payment_method: boolean;
  org_id: string;
  plan: string;
  autumn_enabled?: boolean;
  features?: Record<string, { allowed: boolean; balance: number | null; usage: number | null; included_usage: number | null }>;
}

// ---------------------------------------------------------------------------
// Main Dashboard
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const router = useRouter();
  const { data: session, isPending } = useSession();

  const [org, setOrg] = useState<OrgData | null>(null);
  const [usage, setUsage] = useState<UsageStats | null>(null);
  const [events, setEvents] = useState<UsageEvent[]>([]);
  const [estimatedCost, setEstimatedCost] = useState(0);
  const [keys, setKeys] = useState<KeyInfo[]>([]);
  const [tools, setTools] = useState<ToolManifest[]>([]);
  const [billing, setBilling] = useState<BillingInfo | null>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<'overview' | 'build' | 'tools' | 'keys' | 'activity' | 'billing'>('overview');

  const initialized = useRef(false);

  // ------------------------------------------
  // Load all data via server-side proxy routes
  // ------------------------------------------
  const loadAll = useCallback(async () => {
    try {
      setError(null);

      // 1. org info
      const orgRes = await fetch('/api/my-org');
      if (!orgRes.ok) {
        if (orgRes.status === 404) { router.push('/setup'); return; }
        throw new Error('Failed to load org');
      }
      const orgData = await orgRes.json();
      setOrg({ org_id: orgData.org_id, org_name: orgData.org_name, plan: orgData.plan });

      // 2. All data in parallel via proxy routes (server handles the API key)
      const [usageRes, keysRes, toolsRes, billingRes] = await Promise.allSettled([
        fetch('/api/dashboard/usage').then(r => r.json()),
        fetch('/api/dashboard/keys').then(r => r.json()),
        fetch('/api/dashboard/tools').then(r => r.json()),
        fetch('/api/dashboard/billing').then(r => r.json()),
      ]);

      if (usageRes.status === 'fulfilled') {
        const d = usageRes.value;
        if (d.usage) setUsage(d.usage);
        if (d.detailed?.recent_events) setEvents(d.detailed.recent_events);
        if (d.detailed?.estimated_cost_usd !== undefined) setEstimatedCost(d.detailed.estimated_cost_usd);
      }
      if (keysRes.status === 'fulfilled' && keysRes.value.keys) {
        setKeys(keysRes.value.keys);
      }
      if (toolsRes.status === 'fulfilled' && toolsRes.value.tools) {
        setTools(toolsRes.value.tools);
      }
      if (billingRes.status === 'fulfilled') {
        setBilling(billingRes.value);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load dashboard');
    } finally {
      setLoading(false);
    }
  }, [router]);

  useEffect(() => {
    if (isPending) return;
    if (!session) { router.push('/login'); return; }
    if (!initialized.current) {
      initialized.current = true;
      loadAll();
    }
  }, [session, isPending, router, loadAll]);

  const handleSignOut = async () => {
    await signOut();
    router.push('/');
  };

  if (isPending || loading) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center">
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-white/20 border-t-white/80 rounded-full animate-spin" />
          <span className="text-white/50">Loading dashboard...</span>
        </div>
      </div>
    );
  }

  const hasPayment = billing?.has_payment_method ?? false;

  return (
    <div className="min-h-screen bg-[#030712] text-white">
      {/* Header */}
      <header className="border-b border-white/[0.06] px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-xl text-white" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
            Foundry
          </Link>
          <span className="text-white/20">|</span>
          <span className="text-white/50 text-sm">{org?.org_name}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="hidden sm:inline text-white/40 text-xs">{session?.user.email}</span>
          <span className="px-2 py-0.5 text-[10px] uppercase tracking-wider bg-white/[0.06] border border-white/[0.08] text-white/50">
            {org?.plan ?? 'paygo'}
          </span>
          <button onClick={handleSignOut} className="text-sm text-white/40 hover:text-white transition-colors">
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-5xl mx-auto px-6 py-8">
        {/* Payment required banner */}
        {!hasPayment && (
          <div className="mb-6 p-4 bg-amber-500/10 border border-amber-500/20 flex items-start gap-4">
            <svg className="w-5 h-5 text-amber-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
            </svg>
            <div className="flex-1">
              <p className="text-amber-400 text-sm font-medium">Add a payment method to get started</p>
              <p className="text-amber-400/60 text-xs mt-0.5">
                Building tools and creating API keys requires a payment method on file. You only pay for what you use.
              </p>
            </div>
            <button
              onClick={() => setTab('billing')}
              className="shrink-0 px-4 py-2 bg-amber-500 text-black text-sm font-medium hover:bg-amber-400 transition-colors"
            >
              Add Card
            </button>
          </div>
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex justify-between">
            <span>{error}</span>
            <button onClick={() => setError(null)}>✕</button>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-0 mb-8 border-b border-white/[0.06] overflow-x-auto">
          {(['overview', 'build', 'tools', 'keys', 'activity', 'billing'] as const).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium capitalize transition-colors border-b-2 -mb-px whitespace-nowrap ${
                tab === t ? 'text-white border-white' : 'text-white/40 border-transparent hover:text-white/60'
              }`}
            >
              {t === 'build' ? '+ Build Tool' : t}
            </button>
          ))}
        </div>

        {tab === 'overview' && (
          <OverviewTab usage={usage} tools={tools} keys={keys} estimatedCost={estimatedCost} hasPayment={hasPayment} onGoToBilling={() => setTab('billing')} onGoBuild={() => setTab('build')} />
        )}
        {tab === 'build' && (
          <BuildTab hasPayment={hasPayment} orgId={org?.org_id ?? ''} onToolBuilt={(tool) => { setTools(prev => [tool, ...prev]); setTab('tools'); }} onGoToBilling={() => setTab('billing')} />
        )}
        {tab === 'tools' && (
          <ToolsTab tools={tools} />
        )}
        {tab === 'keys' && (
          <KeysTab keys={keys} hasPayment={hasPayment} onKeysChanged={setKeys} onGoToBilling={() => setTab('billing')} />
        )}
        {tab === 'activity' && <ActivityTab events={events} />}
        {tab === 'billing' && (
          <BillingTab billing={billing} plan={org?.plan ?? 'paygo'} orgId={org?.org_id ?? ''} onPaymentAdded={() => { setBilling(prev => prev ? { ...prev, has_payment_method: true } : prev); }} />
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview Tab
// ---------------------------------------------------------------------------

function OverviewTab({
  usage, tools, keys, estimatedCost, hasPayment, onGoToBilling, onGoBuild,
}: {
  usage: UsageStats | null;
  tools: ToolManifest[];
  keys: KeyInfo[];
  estimatedCost: number;
  hasPayment: boolean;
  onGoToBilling: () => void;
  onGoBuild: () => void;
}) {
  return (
    <div>
      {/* Usage stats */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <StatCard label="Tool Builds" value={String(usage?.builds ?? 0)} sub={usage?.builds_limit === -1 ? 'unlimited' : `/ ${usage?.builds_limit ?? '—'}`} />
        <StatCard label="Invocations" value={String(usage?.invocations ?? 0)} sub={usage?.invocations_limit === -1 ? 'unlimited' : `/ ${usage?.invocations_limit ?? '—'}`} />
        <StatCard label="Searches" value={String(usage?.searches ?? 0)} sub={usage?.searches_limit === -1 ? 'unlimited' : `/ ${usage?.searches_limit ?? '—'}`} />
        <StatCard label="Est. Cost" value={`$${estimatedCost.toFixed(2)}`} sub="this month" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <StatCard label="Active Tools" value={String(tools.filter(t => t.status === 'ready').length)} sub={`${tools.length} total`} />
        <StatCard label="API Keys" value={String(keys.filter(k => k.is_active).length)} sub="active" />
        <StatCard
          label="Plan"
          value={usage?.plan === 'paygo' ? 'Pay As You Go' : (usage?.plan ?? 'paygo')}
          sub={usage?.plan === 'paygo' ? '$0.015 / CU' : '$49/month'}
        />
      </div>

      {/* CTA */}
      <div className="bg-white/[0.02] border border-white/[0.08] p-8 text-center">
        {!hasPayment ? (
          <>
            <h3 className="text-xl text-white mb-2" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
              Ready to build your first tool?
            </h3>
            <p className="text-white/40 text-sm mb-4">Add a payment method to get started. You only pay for what you use.</p>
            <button onClick={onGoToBilling} className="bg-white text-black px-6 py-2.5 font-medium hover:bg-white/90 transition-colors">
              Add Payment Method
            </button>
          </>
        ) : (
          <>
            <h3 className="text-xl text-white mb-2" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
              Build a tool with AI
            </h3>
            <p className="text-white/40 text-sm mb-4">Describe what you need and Foundry builds it in seconds.</p>
            <button onClick={onGoBuild} className="bg-white text-black px-6 py-2.5 font-medium hover:bg-white/90 transition-colors">
              + Build Tool
            </button>
          </>
        )}
      </div>

      {/* SDK quickstart */}
      <div className="mt-8 bg-white/[0.02] border border-white/[0.08] p-6">
        <h3 className="text-white/60 text-sm uppercase tracking-wider mb-4">SDK Quickstart</h3>
        <pre className="bg-black/40 p-4 text-sm font-mono text-green-300 overflow-x-auto">{`pip install foundry-sdk

from foundry import Foundry
client = Foundry(api_key="your-fnd_... key")

tool = client.create("Calculate compound interest")
result = tool.invoke(principal=1000, rate=0.05, time=10)
print(result.result)`}</pre>
      </div>
    </div>
  );
}

function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-white/[0.03] border border-white/[0.06] p-5">
      <p className="text-white/40 text-xs uppercase tracking-wider mb-2">{label}</p>
      <p className="text-2xl text-white font-light mb-1">{value}</p>
      <p className="text-white/30 text-xs">{sub}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Build Tool Tab
// ---------------------------------------------------------------------------

function BuildTab({
  hasPayment, orgId, onToolBuilt, onGoToBilling,
}: {
  hasPayment: boolean;
  orgId: string;
  onToolBuilt: (tool: ToolManifest) => void;
  onGoToBilling: () => void;
}) {
  const [description, setDescription] = useState('');
  const [building, setBuilding] = useState(false);
  const [result, setResult] = useState<{ success: boolean; tool?: ToolManifest; error?: string } | null>(null);

  const examples = [
    'Calculate compound interest given principal, rate, and time period',
    'Convert between temperature units (Celsius, Fahrenheit, Kelvin)',
    'Validate an email address and return a formatted report',
    'Summarize a block of text to key bullet points',
    'Parse a CSV string and return it as JSON with column headers',
  ];

  const handleBuild = async () => {
    if (!description.trim()) return;
    setBuilding(true);
    setResult(null);

    try {
      const res = await fetch('/api/dashboard/tools', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description: description.trim() }),
      });
      const data = await res.json();

      if (res.status === 402) {
        setResult({ success: false, error: 'payment_required' });
        return;
      }
      if (!res.ok || data.status === 'failed') {
        setResult({ success: false, error: data.message || data.error || 'Build failed' });
        return;
      }

      // Build succeeded
      const tool: ToolManifest = {
        tool_id: data.tool_id,
        name: description.slice(0, 60),
        description: description,
        status: 'ready',
        input_schema: {},
        invoke_url: data.invoke_url || '',
        created_at: new Date().toISOString(),
      };
      setResult({ success: true, tool });
      onToolBuilt(tool);
    } catch (err) {
      setResult({ success: false, error: err instanceof Error ? err.message : 'Build failed' });
    } finally {
      setBuilding(false);
    }
  };

  if (!hasPayment) {
    return (
      <div className="text-center py-16">
        <div className="inline-flex items-center justify-center w-16 h-16 bg-amber-500/10 border border-amber-500/20 mb-6">
          <svg className="w-8 h-8 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" />
          </svg>
        </div>
        <h3 className="text-xl text-white mb-2" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
          Payment required to build tools
        </h3>
        <p className="text-white/40 text-sm mb-6 max-w-sm mx-auto">
          Add a payment method to start building. You only pay $0.015 per tool build.
        </p>
        <button onClick={onGoToBilling} className="bg-white text-black px-8 py-3 font-medium hover:bg-white/90 transition-colors">
          Add Payment Method
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-2xl">
      <h2 className="text-2xl mb-2" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
        Build a Tool
      </h2>
      <p className="text-white/40 text-sm mb-6">
        Describe what you need in plain English. Foundry uses AI to generate a working tool in seconds.
      </p>

      <div className="mb-4">
        <label className="block text-white/60 text-sm mb-2">What should this tool do?</label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          rows={4}
          placeholder="e.g. Calculate the monthly payment for a loan given principal, interest rate, and term in months"
          className="w-full bg-white/[0.03] border border-white/[0.1] px-4 py-3 text-white placeholder-white/25 focus:outline-none focus:border-white/30 resize-none text-sm"
          disabled={building}
        />
        <p className="text-white/25 text-xs mt-1">{description.length}/2000</p>
      </div>

      {/* Examples */}
      <div className="mb-6">
        <p className="text-white/30 text-xs mb-2">Try an example:</p>
        <div className="flex flex-wrap gap-2">
          {examples.map((ex, i) => (
            <button
              key={i}
              onClick={() => setDescription(ex)}
              className="text-xs px-3 py-1.5 bg-white/[0.04] border border-white/[0.08] text-white/50 hover:text-white hover:border-white/20 transition-colors"
            >
              {ex.slice(0, 40)}...
            </button>
          ))}
        </div>
      </div>

      <button
        onClick={handleBuild}
        disabled={building || !description.trim()}
        className="w-full bg-white text-black py-3 font-medium hover:bg-white/90 transition-colors disabled:opacity-40 flex items-center justify-center gap-2"
      >
        {building ? (
          <>
            <div className="w-4 h-4 border-2 border-black/30 border-t-black rounded-full animate-spin" />
            Building tool... (10–30s)
          </>
        ) : (
          'Build Tool'
        )}
      </button>

      {result && (
        <div className={`mt-6 p-5 border ${result.success ? 'bg-green-500/10 border-green-500/20' : 'bg-red-500/10 border-red-500/20'}`}>
          {result.success && result.tool ? (
            <>
              <div className="flex items-center gap-2 mb-3">
                <svg className="w-5 h-5 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-green-400 font-medium">Tool built successfully!</span>
              </div>
              <p className="text-white/60 text-sm mb-2">Tool ID: <code className="text-white/80 font-mono">{result.tool.tool_id}</code></p>
              <p className="text-white/60 text-sm mb-3">Invoke URL: <code className="text-white/80 font-mono text-xs break-all">{result.tool.invoke_url}</code></p>
              <p className="text-white/40 text-xs">Find this tool in the Tools tab to test it.</p>
            </>
          ) : result.error === 'payment_required' ? (
            <div className="flex items-center justify-between">
              <span className="text-amber-400 text-sm">Payment required to build tools.</span>
              <button onClick={onGoToBilling} className="text-xs px-3 py-1.5 bg-amber-500 text-black font-medium">Add Card</button>
            </div>
          ) : (
            <div className="flex items-start gap-2">
              <svg className="w-5 h-5 text-red-400 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
              <div>
                <p className="text-red-400 font-medium text-sm">Build failed</p>
                <p className="text-red-400/70 text-xs mt-1">{result.error}</p>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tools Tab — list + test panel
// ---------------------------------------------------------------------------

function ToolsTab({ tools }: { tools: ToolManifest[] }) {
  const [selected, setSelected] = useState<ToolManifest | null>(null);
  const [testInput, setTestInput] = useState('{}');
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testLoading, setTestLoading] = useState(false);
  const [testError, setTestError] = useState<string | null>(null);

  const handleTest = async () => {
    if (!selected) return;
    setTestLoading(true);
    setTestResult(null);
    setTestError(null);

    let inputData: Record<string, unknown> = {};
    try { inputData = JSON.parse(testInput); } catch { setTestError('Invalid JSON'); setTestLoading(false); return; }

    try {
      const res = await fetch('/api/dashboard/tools/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_id: selected.tool_id, input: inputData }),
      });
      const data = await res.json();
      setTestResult(JSON.stringify(data, null, 2));
    } catch (err) {
      setTestError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setTestLoading(false);
    }
  };

  if (tools.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-white/40 mb-2">No tools yet.</p>
        <p className="text-white/30 text-sm">Go to the Build tab to create your first tool.</p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Tool list */}
      <div className="space-y-2">
        <h2 className="text-lg text-white/70 mb-4 font-medium">Your Tools ({tools.length})</h2>
        {tools.map(tool => (
          <div
            key={tool.tool_id}
            onClick={() => {
              setSelected(tool);
              // Auto-fill input from schema
              if (tool.input_schema && typeof tool.input_schema === 'object' && 'properties' in tool.input_schema) {
                const props = tool.input_schema.properties as Record<string, { type?: string }>;
                const ex: Record<string, unknown> = {};
                for (const [k, v] of Object.entries(props)) {
                  ex[k] = v.type === 'number' || v.type === 'integer' ? 0 : v.type === 'boolean' ? false : '';
                }
                setTestInput(JSON.stringify(ex, null, 2));
              } else {
                setTestInput('{}');
              }
              setTestResult(null);
              setTestError(null);
            }}
            className={`p-4 border cursor-pointer transition-all ${selected?.tool_id === tool.tool_id ? 'border-white/30 bg-white/[0.05]' : 'border-white/[0.07] bg-white/[0.02] hover:border-white/20'}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm font-medium truncate">{tool.name}</p>
                <p className="text-white/40 text-xs mt-0.5 truncate">{tool.description}</p>
              </div>
              <span className={`ml-2 shrink-0 px-1.5 py-0.5 text-[9px] uppercase tracking-wider border ${
                tool.status === 'ready' ? 'text-green-400 border-green-500/20 bg-green-500/10' : 'text-yellow-400 border-yellow-500/20 bg-yellow-500/10'
              }`}>{tool.status}</span>
            </div>
            <p className="text-white/25 text-xs font-mono mt-2">{tool.tool_id}</p>
          </div>
        ))}
      </div>

      {/* Test panel */}
      <div className="bg-white/[0.02] border border-white/[0.07] p-5">
        {selected ? (
          <>
            <h3 className="text-white font-medium mb-1 text-sm">{selected.name}</h3>
            <p className="text-white/30 text-xs mb-4">Test with JSON input below</p>

            <label className="block text-white/40 text-xs uppercase tracking-wider mb-1.5">Input</label>
            <textarea
              value={testInput}
              onChange={e => setTestInput(e.target.value)}
              rows={6}
              className="w-full bg-black/30 border border-white/[0.08] px-3 py-2.5 text-sm font-mono text-white focus:outline-none focus:border-white/20 mb-3 resize-none"
            />

            <button
              onClick={handleTest}
              disabled={testLoading || selected.status !== 'ready'}
              className="w-full bg-white text-black py-2.5 text-sm font-medium hover:bg-white/90 transition-colors disabled:opacity-50 mb-4"
            >
              {testLoading ? 'Running...' : 'Run Tool'}
            </button>

            {testError && (
              <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-mono mb-3">{testError}</div>
            )}
            {testResult && (
              <>
                <label className="block text-white/40 text-xs uppercase tracking-wider mb-1.5">Result</label>
                <pre className="bg-black/40 border border-white/[0.06] p-3 text-xs font-mono text-green-300 overflow-auto max-h-52">{testResult}</pre>
              </>
            )}

            <div className="mt-4 pt-4 border-t border-white/[0.06]">
              <p className="text-white/20 text-xs font-mono break-all">{selected.invoke_url}</p>
            </div>
          </>
        ) : (
          <div className="h-full flex items-center justify-center py-16">
            <p className="text-white/25 text-sm">← Select a tool to test it</p>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Keys Tab
// ---------------------------------------------------------------------------

function KeysTab({
  keys, hasPayment, onKeysChanged, onGoToBilling,
}: {
  keys: KeyInfo[];
  hasPayment: boolean;
  onKeysChanged: (keys: KeyInfo[]) => void;
  onGoToBilling: () => void;
}) {
  const [newKeyName, setNewKeyName] = useState('');
  const [creating, setCreating] = useState(false);
  const [newKey, setNewKey] = useState<{ key: string; name: string } | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    try {
      const res = await fetch('/api/dashboard/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newKeyName.trim() || 'Default' }),
      });
      const data = await res.json();
      if (res.status === 402) {
        setError('payment_required');
        return;
      }
      if (!res.ok) { setError(data.message || data.error || 'Failed'); return; }
      setNewKey({ key: data.key, name: data.name });
      setNewKeyName('');
      // Refresh list
      const listRes = await fetch('/api/dashboard/keys');
      const listData = await listRes.json();
      if (listData.keys) onKeysChanged(listData.keys);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (keyId: string) => {
    const res = await fetch(`/api/dashboard/keys?key_id=${keyId}`, { method: 'DELETE' });
    if (res.ok) onKeysChanged(keys.filter(k => k.key_id !== keyId));
  };

  return (
    <div>
      <h2 className="text-2xl mb-2" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>API Keys</h2>
      <p className="text-white/40 text-sm mb-6">Programmatic access via SDK or REST API. Keys are shown once — copy immediately.</p>

      {/* New key banner */}
      {newKey && (
        <div className="mb-6 p-4 bg-green-500/10 border border-green-500/20">
          <p className="text-green-400 text-sm font-medium mb-2">New key created. Copy now — you won&apos;t see it again.</p>
          <div className="flex items-stretch gap-2">
            <code className="flex-1 bg-black/40 border border-white/[0.08] px-3 py-2 text-sm font-mono text-green-300 break-all select-all">{newKey.key}</code>
            <button
              onClick={() => { navigator.clipboard.writeText(newKey.key); setCopied(true); setTimeout(() => setCopied(false), 2000); }}
              className="px-4 bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30 transition-colors shrink-0"
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
            <button onClick={() => setNewKey(null)} className="px-3 text-white/40 hover:text-white">✕</button>
          </div>
        </div>
      )}

      {/* Payment gate */}
      {!hasPayment ? (
        <div className="p-6 border border-amber-500/20 bg-amber-500/5 mb-6">
          <p className="text-amber-400 text-sm mb-3">A payment method is required to create API keys.</p>
          <button onClick={onGoToBilling} className="px-4 py-2 bg-amber-500 text-black text-sm font-medium hover:bg-amber-400">Add Payment Method</button>
        </div>
      ) : (
        <div className="flex gap-2 mb-6">
          <input
            type="text"
            value={newKeyName}
            onChange={e => setNewKeyName(e.target.value)}
            placeholder="Key name (e.g. Production)"
            className="flex-1 bg-white/[0.04] border border-white/[0.08] px-4 py-2.5 text-white placeholder-white/25 focus:outline-none focus:border-white/20 text-sm"
            onKeyDown={e => e.key === 'Enter' && handleCreate()}
          />
          <button onClick={handleCreate} disabled={creating} className="bg-white text-black px-6 py-2.5 font-medium text-sm hover:bg-white/90 disabled:opacity-50 shrink-0">
            {creating ? 'Creating...' : 'Create Key'}
          </button>
        </div>
      )}

      {error === 'payment_required' && (
        <div className="mb-4 p-3 bg-amber-500/10 border border-amber-500/20 text-amber-400 text-sm">Payment required. <button onClick={onGoToBilling} className="underline">Add card →</button></div>
      )}
      {error && error !== 'payment_required' && (
        <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
      )}

      {/* Keys table */}
      <div className="border border-white/[0.07] overflow-hidden">
        <div className="grid grid-cols-5 gap-4 px-4 py-3 bg-white/[0.02] border-b border-white/[0.07] text-xs text-white/30 uppercase tracking-wider">
          <div>Name</div><div>Prefix</div><div>Created</div><div>Last Used</div><div className="text-right">Actions</div>
        </div>
        {keys.filter(k => k.name !== '__server_session__').length === 0 ? (
          <div className="px-4 py-10 text-center text-white/25 text-sm">No API keys yet. Create one above.</div>
        ) : (
          keys.filter(k => k.name !== '__server_session__').map(key => (
            <div key={key.key_id} className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.04] text-sm items-center">
              <div className="text-white">{key.name}</div>
              <div className="text-white/40 font-mono text-xs">{key.prefix}...</div>
              <div className="text-white/30 text-xs">{new Date(key.created_at).toLocaleDateString()}</div>
              <div className="text-white/30 text-xs">{key.last_used_at ? new Date(key.last_used_at).toLocaleDateString() : 'Never'}</div>
              <div className="text-right">
                <button onClick={() => handleRevoke(key.key_id)} className="text-xs text-red-400/50 hover:text-red-400 transition-colors">Revoke</button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Activity Tab
// ---------------------------------------------------------------------------

function ActivityTab({ events }: { events: UsageEvent[] }) {
  const labels: Record<string, string> = { tool_build: 'Build', tool_invoke: 'Invoke', search: 'Search' };
  const colors: Record<string, string> = { tool_build: 'text-pink-400', tool_invoke: 'text-orange-400', search: 'text-green-400' };

  if (events.length === 0) {
    return (
      <div className="text-center py-16">
        <p className="text-white/40 mb-2">No activity yet.</p>
        <p className="text-white/30 text-sm">API calls will appear here as you use Foundry.</p>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-2xl mb-4" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>Recent Activity</h2>
      <div className="border border-white/[0.07] overflow-hidden">
        <div className="grid grid-cols-5 gap-4 px-4 py-3 bg-white/[0.02] border-b border-white/[0.07] text-xs text-white/30 uppercase tracking-wider">
          <div>Type</div><div>Tool</div><div>Duration</div><div>Tokens</div><div>Time</div>
        </div>
        {events.map((e, i) => (
          <div key={i} className="grid grid-cols-5 gap-4 px-4 py-3 border-b border-white/[0.03] text-sm items-center">
            <div className={colors[e.event_type] || 'text-white/50'}>{labels[e.event_type] || e.event_type}</div>
            <div className="text-white/40 font-mono text-xs truncate">{e.tool_id || '—'}</div>
            <div className="text-white/30 text-xs">{e.execution_time_ms > 0 ? `${e.execution_time_ms}ms` : '—'}</div>
            <div className="text-white/30 text-xs">{e.tokens_used > 0 ? e.tokens_used.toLocaleString() : '—'}</div>
            <div className="text-white/25 text-xs">{new Date(e.created_at).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Billing Tab
// ---------------------------------------------------------------------------

function BillingTab({
  billing, plan, orgId, onPaymentAdded,
}: {
  billing: BillingInfo | null;
  plan: string;
  orgId: string;
  onPaymentAdded: () => void;
}) {
  const [loading, setLoading] = useState(false);

  const handleCheckout = async (productId: string) => {
    setLoading(true);
    try {
      const res = await fetch('/api/dashboard/billing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId }),
      });
      const data = await res.json();
      if (data.checkout_url) {
        window.location.href = data.checkout_url;
      }
    } finally {
      setLoading(false);
    }
  };

  const hasPaid = billing?.has_payment_method;

  return (
    <div className="max-w-lg">
      <h2 className="text-2xl mb-6" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>Billing</h2>

      {/* Payment status */}
      <div className={`p-5 border mb-6 ${hasPaid ? 'border-green-500/20 bg-green-500/5' : 'border-amber-500/20 bg-amber-500/5'}`}>
        <div className="flex items-center gap-3">
          <div className={`w-2.5 h-2.5 rounded-full ${hasPaid ? 'bg-green-400' : 'bg-amber-400'}`} />
          <div>
            <p className={`text-sm font-medium ${hasPaid ? 'text-green-400' : 'text-amber-400'}`}>
              {hasPaid ? 'Payment method on file' : 'No payment method'}
            </p>
            <p className="text-white/40 text-xs mt-0.5">
              {hasPaid
                ? 'Your account is active. Usage is billed monthly.'
                : 'Add a card to build tools and create API keys.'}
            </p>
          </div>
        </div>
      </div>

      {/* Plans */}
      <div className="space-y-4 mb-6">
        <div className={`p-5 border ${plan === 'paygo' ? 'border-white/30' : 'border-white/[0.07]'}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-white font-medium">Pay As You Go</span>
            {plan === 'paygo' && <span className="text-xs px-2 py-0.5 bg-white/10 text-white/60 border border-white/20">Current</span>}
          </div>
          <p className="text-white/40 text-sm mb-3">$0.015 per build · $0.001 per invocation · No monthly fee</p>
          {!hasPaid && (
            <button
              onClick={() => handleCheckout('paygo')}
              disabled={loading}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-white/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : 'Add Card & Activate'}
            </button>
          )}
        </div>

        <div className={`p-5 border ${plan === 'pro' ? 'border-white/30' : 'border-white/[0.07]'}`}>
          <div className="flex items-center justify-between mb-1">
            <span className="text-white font-medium">Pro</span>
            {plan === 'pro' && <span className="text-xs px-2 py-0.5 bg-white/10 text-white/60 border border-white/20">Current</span>}
          </div>
          <p className="text-white/40 text-sm mb-3">$49/month · 10,000 CU included · then $0.008 / CU</p>
          {plan !== 'pro' && (
            <button
              onClick={() => handleCheckout('pro')}
              disabled={loading}
              className="px-4 py-2 bg-white text-black text-sm font-medium hover:bg-white/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Loading...' : hasPaid ? 'Upgrade to Pro' : 'Add Card & Upgrade'}
            </button>
          )}
        </div>
      </div>

      {/* Feature usage */}
      {billing?.autumn_enabled && billing.features && (
        <div className="border border-white/[0.07] p-5">
          <h3 className="text-white/50 text-xs uppercase tracking-wider mb-4">This Month&apos;s Usage</h3>
          <div className="space-y-3">
            {Object.entries(billing.features).map(([featureId, info]) => (
              <div key={featureId}>
                <div className="flex justify-between text-sm mb-1">
                  <span className="text-white/60 capitalize">{featureId}</span>
                  <span className="text-white/40 text-xs">
                    {info.usage ?? 0}{info.included_usage ? ` / ${info.included_usage}` : ''}
                  </span>
                </div>
                {info.included_usage && info.included_usage > 0 && (
                  <div className="h-1 bg-white/[0.06] overflow-hidden">
                    <div
                      className="h-full bg-white/40"
                      style={{ width: `${Math.min(100, ((info.usage ?? 0) / info.included_usage) * 100)}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
