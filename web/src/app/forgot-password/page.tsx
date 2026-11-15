'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Loader2, Mail } from 'lucide-react';
import AuthShell, {
  errorClass,
  inputClass,
  labelClass,
  linkClass,
  noticeClass,
  primaryButtonClass,
} from '../../components/AuthShell';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);
    try {
      const res = await fetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed');
      setSent(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Forgot password">
      {sent ? (
        <div className="space-y-4">
          <div className={noticeClass}>
            If an account exists for {email}, we sent a reset link. It expires in 30 minutes.
          </div>
          <p className="text-center text-xs text-neutral-500">
            Nothing after a few minutes? Check spam, or try again.
          </p>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            Enter your email and we will send you a link to choose a new password.
          </p>
          <div>
            <label className={labelClass}>Email</label>
            <div className="relative">
              <Mail className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
              <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
                className={inputClass} placeholder="you@example.com" />
            </div>
          </div>
          {error && <div className={errorClass}>{error}</div>}
          <button type="submit" disabled={isLoading} className={primaryButtonClass}>
            {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Send reset link'}
          </button>
        </form>
      )}
      <p className="text-center text-xs text-neutral-500 mt-6">
        <Link href="/sign-in" className={linkClass}>Back to sign in</Link>
      </p>
    </AuthShell>
  );
}
