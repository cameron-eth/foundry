'use client';

/**
 * /setup — Shown to social auth (GitHub/Google) users after OAuth callback.
 * They have a Better Auth account but no org yet. We collect the org name here.
 */

import Link from 'next/link';
import { useState, Suspense, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useSession } from '@/lib/auth-client';

function SetupForm() {
  const router = useRouter();
  const { data: session, isPending } = useSession();
  const [orgName, setOrgName] = useState('');
  const [plan, setPlan] = useState<'paygo' | 'pro'>('paygo');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  // Pre-fill org name from the user's name
  useEffect(() => {
    if (session?.user?.name && !orgName) {
      setOrgName(session.user.name);
    }
  }, [session, orgName]);

  // If not authenticated, redirect to signup
  useEffect(() => {
    if (!isPending && !session) {
      router.push('/signup');
    }
  }, [isPending, session, router]);

  const handleSetup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const res = await fetch('/api/setup-org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orgName: orgName.trim(), plan }),
      });

      const data = await res.json();

      if (!res.ok) {
        // If user already has an org, go straight to dashboard
        if (res.status === 409 && data.error?.includes('already have an organization')) {
          router.push('/dashboard');
          return;
        }
        setError(data.error ?? 'Failed to create organization');
        return;
      }

      setCreatedKey(data.api_key);
    } catch {
      setError('Could not connect. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (createdKey) {
      navigator.clipboard.writeText(createdKey);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  if (isPending) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center">
        <div className="text-white/40">Loading...</div>
      </div>
    );
  }

  if (createdKey) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <Link href="/" className="text-3xl text-white" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
              Foundry
            </Link>
          </div>
          <div className="bg-white/[0.03] border border-white/[0.08] p-8">
            <div className="text-center mb-6">
              <div className="inline-flex items-center justify-center w-12 h-12 bg-green-500/10 border border-green-500/20 mb-4">
                <svg className="w-6 h-6 text-green-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-2xl text-white mb-1" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
                You&apos;re all set!
              </h2>
              <p className="text-white/50 text-sm">Save your API key — it will not be shown again.</p>
            </div>
            <div className="mb-6">
              <label className="block text-white/60 text-xs uppercase tracking-wider mb-2">API Key (for SDK/programmatic access)</label>
              <div className="flex items-stretch gap-2">
                <code className="flex-1 bg-black/40 border border-white/[0.08] px-3 py-2.5 text-sm font-mono text-green-300 break-all select-all">
                  {createdKey}
                </code>
                <button
                  onClick={handleCopy}
                  className="px-4 bg-white/[0.05] border border-white/[0.08] text-white/70 text-sm hover:bg-white/[0.08] transition-colors shrink-0"
                >
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <p className="text-white/30 text-xs mt-2">Use this with the Foundry SDK. You can create more keys from the dashboard.</p>
            </div>
            <button onClick={() => router.push('/dashboard')} className="w-full bg-white text-black py-3 font-medium hover:bg-white/90 transition-colors">
              Go to Dashboard
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#030712] flex items-center justify-center px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <Link href="/" className="text-3xl text-white" style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}>
            Foundry
          </Link>
          <p className="text-white/50 mt-2">One more step — set up your workspace</p>
        </div>

        <div className="bg-white/[0.03] border border-white/[0.08] p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm">{error}</div>
          )}

          {session?.user && (
            <div className="flex items-center gap-3 mb-6 p-3 bg-white/[0.03] border border-white/[0.06]">
              <div className="w-8 h-8 bg-white/10 rounded-full flex items-center justify-center text-white text-sm font-medium">
                {session.user.name?.[0]?.toUpperCase() ?? session.user.email?.[0]?.toUpperCase() ?? '?'}
              </div>
              <div>
                <p className="text-white text-sm">{session.user.name || 'New user'}</p>
                <p className="text-white/40 text-xs">{session.user.email}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleSetup} className="space-y-4">
            <div>
              <label className="block text-white/60 text-sm mb-1.5">Organization / Project Name</label>
              <input
                type="text"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                className="w-full bg-white/[0.05] border border-white/[0.1] px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/20"
                placeholder="Acme Labs"
                required
              />
            </div>

            <div>
              <label className="block text-white/60 text-sm mb-1.5">Plan</label>
              <div className="grid grid-cols-2 gap-2">
                {(['paygo', 'pro'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPlan(p)}
                    className={`py-2.5 text-sm font-medium border transition-colors ${
                      plan === p
                        ? 'bg-white text-black border-white'
                        : 'bg-white/[0.03] text-white/60 border-white/[0.08] hover:border-white/20'
                    }`}
                  >
                    {p === 'paygo' ? 'Pay As You Go' : 'Pro'}
                  </button>
                ))}
              </div>
              <p className="text-white/30 text-xs mt-1.5">
                {plan === 'paygo' && 'No monthly fee — $0.015 / CU, pay for what you use'}
                {plan === 'pro' && '$49/mo — 10,000 CU included, then $0.008 / CU'}
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-white text-black py-3 font-medium hover:bg-white/90 transition-colors disabled:opacity-50 mt-2"
            >
              {loading ? 'Setting up...' : 'Create Workspace'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function SetupPage() {
  return (
    <Suspense>
      <SetupForm />
    </Suspense>
  );
}
