'use client';

import { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Loader2, Lock } from 'lucide-react';
import AuthShell, {
  errorClass,
  inputClass,
  labelClass,
  linkClass,
  primaryButtonClass,
} from '../../components/AuthShell';

function ResetPasswordForm() {
  const router = useRouter();
  const token = useSearchParams().get('token');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  if (!token) {
    return (
      <AuthShell title="Reset password">
        <p className="text-sm text-center text-neutral-600 dark:text-neutral-400">
          This reset link is invalid.{' '}
          <Link href="/forgot-password" className={linkClass}>Request a new one</Link>
        </p>
      </AuthShell>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (password !== confirm) {
      setError('Passwords do not match');
      return;
    }
    setIsLoading(true);
    try {
      const res = await fetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Reset failed');
      router.push('/sign-in?reset=1');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Reset failed');
      setIsLoading(false);
    }
  };

  return (
    <AuthShell title="Choose a new password">
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className={labelClass}>New password</label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)}
              className={inputClass} placeholder="Min 8 characters" />
          </div>
        </div>
        <div>
          <label className={labelClass}>Confirm password</label>
          <div className="relative">
            <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-500" />
            <input type="password" required minLength={8} value={confirm} onChange={(e) => setConfirm(e.target.value)}
              className={inputClass} placeholder="Repeat password" />
          </div>
        </div>
        {error && (
          <div className={errorClass}>
            {error}{' '}
            {error.includes('expired') && (
              <Link href="/forgot-password" className="underline">Request a new link</Link>
            )}
          </div>
        )}
        <button type="submit" disabled={isLoading} className={primaryButtonClass}>
          {isLoading ? <Loader2 className="w-5 h-5 animate-spin" /> : 'Update password'}
        </button>
      </form>
    </AuthShell>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense>
      <ResetPasswordForm />
    </Suspense>
  );
}
