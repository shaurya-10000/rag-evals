'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, Loader2, XCircle } from 'lucide-react';
import AuthShell, { linkClass, primaryButtonClass } from '../../components/AuthShell';

function VerifyEmail() {
  const token = useSearchParams().get('token');
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>(token ? 'loading' : 'error');
  const [message, setMessage] = useState(token ? '' : 'This verification link is invalid.');
  const started = useRef(false);

  useEffect(() => {
    if (!token || started.current) return;
    started.current = true;
    (async () => {
      try {
        const res = await fetch('/api/auth/verify-email', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ token }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Verification failed');
        setStatus('success');
      } catch (err) {
        setMessage(err instanceof Error ? err.message : 'Verification failed');
        setStatus('error');
      }
    })();
  }, [token]);

  return (
    <AuthShell title="Email verification">
      <div className="flex flex-col items-center gap-4 text-center">
        {status === 'loading' && <Loader2 className="w-8 h-8 animate-spin text-emerald-400" />}
        {status === 'success' && (
          <>
            <CheckCircle2 className="w-10 h-10 text-emerald-400" />
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              Your email is verified. You can sign in now.
            </p>
            <Link href="/sign-in" className={primaryButtonClass}>Go to sign in</Link>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle className="w-10 h-10 text-red-400" />
            <p className="text-sm text-neutral-600 dark:text-neutral-400">{message}</p>
            <p className="text-xs text-neutral-500">
              If you already verified, just <Link href="/sign-in" className={linkClass}>sign in</Link>.
              Otherwise sign in and use &quot;Resend verification email&quot;.
            </p>
          </>
        )}
      </div>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmail />
    </Suspense>
  );
}
