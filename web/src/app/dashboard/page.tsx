'use client';

import { authClient } from '@/lib/auth/client';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import Link from 'next/link';

interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  created_at: string;
  last_used_at: string | null;
}

interface UsageStats {
  builds: number;
  invocations: number;
  searches: number;
  builds_limit: number;
  invocations_limit: number;
  searches_limit: number;
}

export default function DashboardPage() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [usage, setUsage] = useState<UsageStats>({
    builds: 0, invocations: 0, searches: 0,
    builds_limit: 100, invocations_limit: 1000, searches_limit: 500,
  });
  const [newKeyName, setNewKeyName] = useState('');
  const [newKey, setNewKey] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const checkAuth = async () => {
      try {
        const session = await authClient.getSession();
        if (!session?.data?.user) {
          router.push('/login');
          return;
        }
        setUser(session.data.user);
      } catch {
        router.push('/login');
      } finally {
        setLoading(false);
      }
    };
    checkAuth();
  }, [router]);

  const handleSignOut = async () => {
    await authClient.signOut();
    router.push('/');
  };

  const handleCreateKey = async () => {
    // TODO: Call API to create key
    const mockKey = `fnd_${Math.random().toString(36).substring(2, 14)}${Math.random().toString(36).substring(2, 14)}`;
    setNewKey(mockKey);
    setApiKeys(prev => [...prev, {
      id: crypto.randomUUID(),
      name: newKeyName || 'Default',
      prefix: mockKey.substring(0, 8),
      created_at: new Date().toISOString(),
      last_used_at: null,
    }]);
    setNewKeyName('');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0f] flex items-center justify-center">
        <div className="text-white/50">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0a0a0f] text-white">
      {/* Header */}
      <header className="border-b border-white/[0.08] px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-[family-name:var(--font-instrument-serif)] text-2xl text-white">
          Foundry
        </Link>
        <div className="flex items-center gap-4">
          <span className="text-white/50 text-sm">{user?.email}</span>
          <button
            onClick={handleSignOut}
            className="text-sm text-white/50 hover:text-white transition-colors"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-10">
        <h1 className="font-[family-name:var(--font-instrument-serif)] text-4xl mb-2">
          Dashboard
        </h1>
        <p className="text-white/50 mb-10">
          Manage your API keys and monitor usage.
        </p>

        {/* Usage Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-12">
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
        </div>

        {/* API Keys */}
        <div className="mb-12">
          <h2 className="font-[family-name:var(--font-instrument-serif)] text-2xl mb-4">
            API Keys
          </h2>

          {/* New key alert */}
          {newKey && (
            <div className="mb-4 p-4 bg-green-500/10 border border-green-500/20">
              <p className="text-green-400 text-sm font-medium mb-1">
                New API key created. Copy it now - you won&apos;t see it again.
              </p>
              <div className="flex items-center gap-2">
                <code className="bg-black/40 px-3 py-2 text-sm font-mono flex-1 text-green-300">
                  {newKey}
                </code>
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(newKey);
                  }}
                  className="px-3 py-2 bg-green-500/20 text-green-400 text-sm hover:bg-green-500/30 transition-colors"
                >
                  Copy
                </button>
                <button
                  onClick={() => setNewKey(null)}
                  className="px-3 py-2 text-white/50 text-sm hover:text-white transition-colors"
                >
                  Dismiss
                </button>
              </div>
            </div>
          )}

          {/* Create key */}
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              placeholder="Key name (e.g., Production)"
              className="bg-white/[0.05] border border-white/[0.1] px-4 py-2.5 text-white placeholder-white/30 focus:outline-none focus:border-white/20 flex-1"
            />
            <button
              onClick={handleCreateKey}
              className="bg-white text-black px-6 py-2.5 font-medium hover:bg-white/90 transition-colors"
            >
              Create Key
            </button>
          </div>

          {/* Keys table */}
          <div className="border border-white/[0.08]">
            <div className="grid grid-cols-4 gap-4 px-4 py-3 bg-white/[0.03] border-b border-white/[0.08] text-sm text-white/50 uppercase tracking-wider">
              <div>Name</div>
              <div>Key</div>
              <div>Created</div>
              <div>Last Used</div>
            </div>
            {apiKeys.length === 0 ? (
              <div className="px-4 py-8 text-center text-white/30">
                No API keys yet. Create one to get started.
              </div>
            ) : (
              apiKeys.map((key) => (
                <div
                  key={key.id}
                  className="grid grid-cols-4 gap-4 px-4 py-3 border-b border-white/[0.05] text-sm"
                >
                  <div className="text-white">{key.name}</div>
                  <div className="text-white/60 font-mono">{key.prefix}...</div>
                  <div className="text-white/40">
                    {new Date(key.created_at).toLocaleDateString()}
                  </div>
                  <div className="text-white/40">
                    {key.last_used_at
                      ? new Date(key.last_used_at).toLocaleDateString()
                      : 'Never'}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Quick Start */}
        <div>
          <h2 className="font-[family-name:var(--font-instrument-serif)] text-2xl mb-4">
            Quick Start
          </h2>
          <div className="bg-white/[0.03] border border-white/[0.08] p-6">
            <p className="text-white/60 mb-4 text-sm">Install the SDK and start building tools:</p>
            <pre className="bg-black/40 p-4 text-sm font-mono text-green-300 overflow-x-auto">
{`pip install foundry-sdk

from foundry import Foundry

client = Foundry(api_key="your-api-key")

# Create a tool from a description
tool = client.create("Calculate compound interest")
result = tool.invoke(principal=1000, rate=0.05, time=10)
print(result.result)`}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

function UsageCard({ label, current, limit, color }: {
  label: string;
  current: number;
  limit: number;
  color: 'pink' | 'orange' | 'green';
}) {
  const percentage = limit > 0 ? (current / limit) * 100 : 0;
  const colorMap = {
    pink: { bar: 'bg-pink-500', text: 'text-pink-400', bg: 'bg-pink-500/10' },
    orange: { bar: 'bg-orange-500', text: 'text-orange-400', bg: 'bg-orange-500/10' },
    green: { bar: 'bg-green-500', text: 'text-green-400', bg: 'bg-green-500/10' },
  };
  const colors = colorMap[color];

  return (
    <div className="bg-white/[0.03] border border-white/[0.08] p-6">
      <div className="flex items-center justify-between mb-3">
        <span className="text-white/50 text-sm uppercase tracking-wider">{label}</span>
        <span className={`text-xs ${colors.text}`}>{percentage.toFixed(0)}%</span>
      </div>
      <div className="text-3xl font-[family-name:var(--font-instrument-serif)] mb-3">
        {current.toLocaleString()}
        <span className="text-white/30 text-lg"> / {limit.toLocaleString()}</span>
      </div>
      <div className="w-full h-1.5 bg-white/[0.05] rounded-full overflow-hidden">
        <div
          className={`h-full ${colors.bar} transition-all duration-500`}
          style={{ width: `${Math.min(percentage, 100)}%` }}
        />
      </div>
    </div>
  );
}
