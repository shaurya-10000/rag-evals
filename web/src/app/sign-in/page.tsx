'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Mail, Lock } from 'lucide-react';
import AuthShell, {
  errorClass,
  inputClass,
  labelClass,
  linkClass,
  noticeClass,
  primaryButtonClass,
} from '../../components/AuthShell';
import GoogleButton, { OrDivider } from '../../components/GoogleButton';

const URL_ERRORS: Record<string, string> = {
  google_failed: 'Google sign-in failed. Please try again.',
  google_unverified: 'Your Google account email is not verified.',
  google_unavailable: 'Google sign-in is not available right now.',
};

function SignInForm() {
  const router = useRouter();
  const params = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(() => URL_ERRORS[params.get('error') ?? ''] ?? '');
  const [isLoading, setIsLoading] = useState(false);
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');
  const notice = params.get('reset') ? 'Password updated. Sign in with your new password.' : '';

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setNeedsVerification(false);
    setResendState('idle');
    setIsLoading(true);
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (data.detail === 'email_not_verified') {
          setNeedsVerification(true);
          setError('Please verify your email before signing in. Check your inbox for the link.');
          setIsLoading(false);
          return;
        }
        throw new Error(typeof data.detail === 'string' ? data.detail : 'Login failed');
      }
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
      setIsLoading(false);
    }
  };

  const resend = async () => {
    setResendState('sending');
    await fetch('/api/auth/resend-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    }).catch(() => null);
    setResendState('sent');
  };

  return (
    <AuthShell title="Welcome back">
      <GoogleButton />
      <OrDivider />
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>Email</label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className={inputClass} placeholder="you@example.com" />
          </div>
        </div>
        <div>
          <div className="flex items-center justify-between">
            <label className={labelClass}>Password</label>
            <Link href="/forgot-password" className={`text-xs mb-2 ${linkClass}`}>Forgot password?</Link>
          </div>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)}
              className={inputClass} placeholder="••••••••" />
          </div>
        </div>
        {notice && <div className={noticeClass}>{notice}</div>}
        {error && <div className={errorClass}>{error}</div>}
        {needsVerification && (
          <button type="button" onClick={resend} disabled={resendState !== 'idle'}
            className="w-full text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-60">
            {resendState === 'sent'
              ? 'If that account needs verification, a new email is on its way.'
              : resendState === 'sending'
                ? 'Sending...'
                : 'Resend verification email'}
          </button>
        )}
        <button type="submit" disabled={isLoading} className={primaryButtonClass}>
          {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign In'}
        </button>
      </form>
      <p className="text-center text-xs text-neutral-500 mt-6">
        Don&apos;t have an account?{' '}
        <Link href="/sign-up" className={linkClass}>Create one</Link>
      </p>
    </AuthShell>
  );
}

export default function SignInPage() {
  return (
    <Suspense>
      <SignInForm />
    </Suspense>
  );
}
