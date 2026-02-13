'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { register, setStoredApiKey, setStoredOrg, ApiError } from '@/lib/api';

export default function SignupPage() {
  const [orgName, setOrgName] = useState('');
  const [email, setEmail] = useState('');
  const [plan, setPlan] = useState('free');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const router = useRouter();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const result = await register({
        org_name: orgName.trim(),
        email: email.trim() || undefined,
        plan,
      });

      // Store credentials
      setStoredApiKey(result.api_key);
      setStoredOrg({
        org_id: result.org_id,
        org_name: result.org_name,
        plan: result.plan,
      });

      // Show the key so they can copy it
      setCreatedKey(result.api_key);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError('Could not connect to the Foundry API. Please try again.');
      }
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

  // After registration — show the key
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
                Save your API key now. It will not be shown again.
              </p>
            </div>

            <div className="mb-6">
              <label className="block text-white/60 text-xs uppercase tracking-wider mb-2">
                Your API Key
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
                Email <span className="text-white/30">(optional)</span>
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-white/[0.05] border border-white/[0.1] px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/20"
                placeholder="you@company.com"
              />
            </div>

            <div>
              <label className="block text-white/60 text-sm mb-1.5">
                Plan
              </label>
              <div className="grid grid-cols-3 gap-2">
                {(['free', 'pro', 'scale'] as const).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setPlan(p)}
                    className={`py-2.5 text-sm font-medium border transition-colors capitalize ${
                      plan === p
                        ? 'bg-white text-black border-white'
                        : 'bg-white/[0.03] text-white/60 border-white/[0.08] hover:border-white/20'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
              <p className="text-white/30 text-xs mt-1.5">
                {plan === 'free' && '100 builds / 1,000 invocations per month'}
                {plan === 'pro' && '$49/mo — 1,000 builds / 25,000 invocations'}
                {plan === 'scale' && '$199/mo — 10,000 builds / 250,000 invocations'}
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

          {/* Footer */}
          <p className="text-center text-white/40 text-sm mt-6">
            Already have an API key?{' '}
            <Link href="/login" className="text-white hover:text-white/80 underline">
              Sign in
            </Link>
          </p>
        </div>

        {/* Terms */}
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
