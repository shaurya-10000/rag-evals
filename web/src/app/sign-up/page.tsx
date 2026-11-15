'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Loader2, Mail, Lock, User } from 'lucide-react';
import AuthShell, {
  errorClass,
  inputClass,
  labelClass,
  linkClass,
  primaryButtonClass,
} from '../../components/AuthShell';
import GoogleButton, { OrDivider } from '../../components/GoogleButton';

export default function SignUpPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [resendState, setResendState] = useState<'idle' | 'sending' | 'sent'>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch('/api/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Sign up failed');
      setSentTo(email);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign up failed');
    } finally {
      setIsLoading(false);
    }
  };

  const resend = async () => {
    setResendState('sending');
    await fetch('/api/auth/resend-verification', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: sentTo }),
    }).catch(() => null);
    setResendState('sent');
  };

  if (sentTo) {
    return (
      <AuthShell title="Check your email">
        <p className="text-sm text-center text-neutral-600 dark:text-neutral-400 leading-relaxed">
          We sent a verification link to{' '}
          <span className="font-medium text-neutral-900 dark:text-neutral-100">{sentTo}</span>.
          Open it to activate your account, then sign in. It may take a minute and can land in spam.
        </p>
        <button type="button" onClick={resend} disabled={resendState !== 'idle'}
          className="w-full mt-6 text-xs text-emerald-400 hover:text-emerald-300 disabled:opacity-60">
          {resendState === 'sent'
            ? 'Sent again. Give it a minute.'
            : resendState === 'sending'
              ? 'Sending...'
              : 'Resend verification email'}
        </button>
        <p className="text-center text-xs text-neutral-500 mt-4">
          <Link href="/sign-in" className={linkClass}>Back to sign in</Link>
        </p>
      </AuthShell>
    );
  }

  return (
    <AuthShell title="Create an account">
      <GoogleButton label="Sign up with Google" />
      <OrDivider />
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>Username</label>
          <div className="relative">
            <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="text" required minLength={3} value={username} onChange={(e) => setUsername(e.target.value)}
              className={inputClass} placeholder="johndoe" />
          </div>
        </div>
        <div>
          <label className={labelClass}>Email</label>
          <div className="relative">
            <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
              className={inputClass} placeholder="you@example.com" />
          </div>
        </div>
        <div>
          <label className={labelClass}>Password</label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
              className={inputClass} placeholder="Min 8 characters" />
          </div>
        </div>
        {error && <div className={errorClass}>{error}</div>}
        <button type="submit" disabled={isLoading} className={primaryButtonClass}>
          {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Sign Up'}
        </button>
      </form>
      <p className="text-center text-xs text-neutral-500 mt-6">
        Already have an account?{' '}
        <Link href="/sign-in" className={linkClass}>Sign in</Link>
      </p>
    </AuthShell>
  );
}
