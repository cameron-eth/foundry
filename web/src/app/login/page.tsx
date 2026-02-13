'use client';

import Link from 'next/link';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { setStoredApiKey, setStoredOrg, healthCheck, getUsage, ApiError } from '@/lib/api';

export default function LoginPage() {
  const [apiKey, setApiKey] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    const key = apiKey.trim();
    if (!key) {
      setError('Please enter your API key.');
      setLoading(false);
      return;
    }

    try {
      // Store the key temporarily so getUsage() picks it up
      setStoredApiKey(key);

      // Validate by calling usage — requires auth
      const usage = await getUsage();

      // If we got here the key is valid — store org info
      setStoredOrg({
        org_id: '',
        org_name: '',
        plan: usage.plan,
      });

      router.push('/dashboard');
    } catch (err) {
      // Clear the invalid key
      setStoredApiKey('');
      if (err instanceof ApiError) {
        if (err.status === 401) {
          setError('Invalid API key. Check that you copied the full key.');
        } else if (err.status === 429) {
          setError('Rate limited. Please try again in a moment.');
        } else {
          setError(err.message);
        }
      } else {
        setError('Could not connect to the Foundry API. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

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
          <p className="text-white/50 mt-2">Sign in with your API key</p>
        </div>

        {/* Card */}
        <div className="bg-white/[0.03] border border-white/[0.08] p-8">
          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/20 text-red-400 text-sm">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <label className="block text-white/60 text-sm mb-1.5">
                API Key
              </label>
              <input
                type="password"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                className="w-full bg-white/[0.05] border border-white/[0.1] px-4 py-3 text-white placeholder-white/30 focus:outline-none focus:border-white/20 font-mono text-sm"
                placeholder="fnd_..."
                autoComplete="off"
                required
              />
              <p className="text-white/30 text-xs mt-1.5">
                Your API key was shown once when you registered. Paste it here.
              </p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-white text-black py-3 font-medium hover:bg-white/90 transition-colors disabled:opacity-50"
            >
              {loading ? 'Verifying...' : 'Sign In'}
            </button>
          </form>

          {/* Divider */}
          <div className="relative my-6">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-white/[0.08]" />
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-[#030712] text-white/40">or</span>
            </div>
          </div>

          <Link
            href="/signup"
            className="block w-full text-center bg-white/[0.05] border border-white/[0.1] py-3 text-white font-medium hover:bg-white/[0.08] transition-colors"
          >
            Create a new account
          </Link>

          <p className="text-center text-white/30 text-xs mt-6">
            Need an API key?{' '}
            <Link href="/signup" className="text-white/60 hover:text-white underline">
              Register your organization
            </Link>{' '}
            to get one.
          </p>
        </div>
      </div>
    </div>
  );
}
