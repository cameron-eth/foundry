'use client';

import Link from 'next/link';
import { useState, Suspense } from 'react';
import { useRouter } from 'next/navigation';
import { signUp } from '@/lib/auth-client';

function SignupForm() {
  const router = useRouter();
  const [orgName, setOrgName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [plan, setPlan] = useState<'paygo' | 'pro'>('paygo');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Step 1: Create Better Auth user
      const result = await signUp.email({
        email: email.trim(),
        password,
        name: orgName.trim(),
      });

      if (result.error) {
        setError(result.error.message ?? 'Signup failed');
        return;
      }

      // Step 2: Create org + API key server-side
      const res = await fetch('/api/setup-org', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ orgName: orgName.trim(), plan }),
      });

      const data = await res.json();
      if (!res.ok) {
        setError(data.error ?? 'Failed to create organization');
        return;
      }

      // Step 3: Show the API key once
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

  // After signup — show the API key once
  if (createdKey) {
    return (
      <div className="min-h-screen bg-[#030712] flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <div className="text-center mb-8">
            <Link
              href="/"
              className="text-3xl text-white"
              style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
            >
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
              <h2
                className="text-2xl text-white mb-1"
                style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
              >
                Account created
              </h2>
              <p className="text-white/50 text-sm">
                Save your API key for SDK access. It will not be shown again.
              </p>
            </div>

            <div className="mb-6">
              <label className="block text-white/60 text-xs uppercase tracking-wider mb-2">
                Your API Key (for programmatic access)
              </label>
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
              <p className="text-white/30 text-xs mt-2">
                Use this key with the Foundry SDK or API. You can create more keys from the dashboard.
              </p>
            </div>

            <button
              onClick={() => router.push('/dashboard')}
              className="w-full bg-white text-black py-3 font-medium hover:bg-white/90 transition-colors"
            >
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
        {/* Logo */}
        <div className="text-center mb-8">
          <Link
            href="/"
            className="text-3xl text-white"
            style={{ fontFamily: 'var(--font-instrument), Georgia, serif' }}
          >
            Foundry
          </Link>
          <p className="text-white/50 mt-2">Create your account</p>
        </div>

        {/* Card */}
        <div className="bg-white/[0.03] border border-white/[0.08] p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleSignup} className="space-y-4">
            <div>
              <label className="block text-white/60 text-sm mb-1.5">
                Organization Name
              </label>
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
              <label className="block text-white/60 text-sm mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-white/[0.05] border border-white/[0.1] px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/20"
                placeholder="you@company.com"
                required
              />
            </div>

            <div>
              <label className="block text-white/60 text-sm mb-1.5">
                Password
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full bg-white/[0.05] border border-white/[0.1] px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/20"
                placeholder="Min. 8 characters"
                minLength={8}
                required
              />
            </div>

            <div>
              <label className="block text-white/60 text-sm mb-1.5">
                Plan
              </label>
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
              {loading ? 'Creating account...' : 'Create Account'}
            </button>
          </form>

          <p className="text-center text-white/40 text-sm mt-6">
            Already have an account?{' '}
            <Link href="/login" className="text-white hover:text-white/80 underline">
              Sign in
            </Link>
          </p>
        </div>

        <p className="text-center text-white/30 text-xs mt-4">
          By creating an account, you agree to our{' '}
          <Link href="/terms" className="underline">Terms of Service</Link>
          {' '}and{' '}
          <Link href="/privacy" className="underline">Privacy Policy</Link>
        </p>
      </div>
    </div>
  );
}

export default function SignupPage() {
  return (
    <Suspense>
      <SignupForm />
    </Suspense>
  );
}
