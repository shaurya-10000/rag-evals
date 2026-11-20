'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type FormEvent, type ReactNode } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { ArrowLeft, Loader2, LogOut, Monitor, Trash2 } from 'lucide-react';

type Account = { email: string; username: string; has_password: boolean; google_linked: boolean };
type SessionInfo = { id: string; device: string; created_at: string; last_seen_at: string; current: boolean };
type Notice = { type: 'ok' | 'error'; text: string };

class SessionExpiredError extends Error {
  constructor() {
    super('Your session has expired. Please sign in again.');
  }
}

async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init });
  const data = (await res.json().catch(() => null)) as { detail?: unknown; error?: string } | null;
  if (res.status === 401) throw new SessionExpiredError();
  if (!res.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : data?.error;
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return data as T;
}

const post = (body: unknown): RequestInit => ({
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

const errMsg = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');

const inputCls =
  'w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-xl py-2 px-3 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50 focus:border-accent-500 transition-all';
const ghostBtn =
  'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-md transition-colors disabled:opacity-50';
const primaryBtn =
  'flex items-center justify-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-medium shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed';

function Card({ title, hint, danger, children }: { title: string; hint?: string; danger?: boolean; children: ReactNode }) {
  return (
    <section
      className={`rounded-2xl border bg-white dark:bg-neutral-900/50 p-4 md:p-5 shadow-sm ${
        danger ? 'border-red-500/30' : 'border-neutral-200 dark:border-neutral-800'
      }`}
    >
      <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">{title}</h3>
      {hint && <p className="text-xs text-neutral-500 mt-1">{hint}</p>}
      <div className="mt-4">{children}</div>
    </section>
  );
}

function NoticeBar({ notice }: { notice: Notice | null }) {
  if (!notice) return null;
  return (
    <div
      className={`mt-3 p-2 rounded-lg text-xs text-center font-medium ${
        notice.type === 'error'
          ? 'bg-red-500/10 text-red-500 border border-red-500/20'
          : 'bg-accent-500/10 text-accent-600 border border-accent-500/20'
      }`}
    >
      {notice.text}
    </div>
  );
}

function PasswordCard({ hasPassword, onChanged }: { hasPassword: boolean; onChanged: () => void }) {
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  if (!hasPassword) {
    return (
      <Card title="Password">
        <p className="text-xs text-neutral-500">
          This account signs in with Google and has no password.{' '}
          <Link href="/forgot-password" className="text-accent-600 hover:underline">
            Set one with Forgot password
          </Link>
          .
        </p>
      </Card>
    );
  }

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      setNotice({ type: 'error', text: 'The new passwords do not match.' });
      return;
    }
    setBusy(true);
    setNotice(null);
    try {
      await api('/api/account/password', post({ current_password: current, new_password: next }));
      setCurrent('');
      setNext('');
      setConfirm('');
      setNotice({ type: 'ok', text: 'Password changed. Your other devices were signed out.' });
      onChanged();
    } catch (err) {
      setNotice({ type: 'error', text: errMsg(err) });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card title="Change password" hint="Changing it signs you out everywhere except this device.">
      <form onSubmit={submit} className="space-y-3">
        <input type="password" autoComplete="current-password" placeholder="Current password" value={current} onChange={(e) => setCurrent(e.target.value)} className={inputCls} />
        <input type="password" autoComplete="new-password" placeholder="New password" value={next} onChange={(e) => setNext(e.target.value)} className={inputCls} />
        <input type="password" autoComplete="new-password" placeholder="Confirm new password" value={confirm} onChange={(e) => setConfirm(e.target.value)} className={inputCls} />
        <button type="submit" disabled={busy || !current || !next || !confirm} className={primaryBtn} style={{ backgroundColor: 'var(--accent-600)' }}>
          {busy && <Loader2 className="w-4 h-4 animate-spin" />} Update password
        </button>
      </form>
      <NoticeBar notice={notice} />
    </Card>
  );
}

function SessionsCard({ sessions, reload }: { sessions: SessionInfo[]; reload: () => void }) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<Notice | null>(null);

  const run = async (id: string, action: () => Promise<unknown>, okText: string) => {
    setBusyId(id);
    setNotice(null);
    try {
      await action();
      setNotice({ type: 'ok', text: okText });
      reload();
    } catch (err) {
      setNotice({ type: 'error', text: errMsg(err) });
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Card title="Active sessions" hint="Devices currently signed in to your account.">
      <ul className="space-y-2">
        {sessions.map((s) => (
          <li key={s.id} className="flex items-center gap-3 rounded-xl border border-neutral-200 dark:border-neutral-800 p-3">
            <Monitor className="w-4 h-4 text-accent-500 shrink-0" />
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-neutral-900 dark:text-neutral-100 truncate">
                {s.device} {s.current && <span className="ml-1 text-[10px] font-semibold text-accent-600">This device</span>}
              </p>
              <p className="text-[11px] text-neutral-500">
                Active {formatDistanceToNow(new Date(s.last_seen_at), { addSuffix: true })}
              </p>
            </div>
            {!s.current && (
              <button
                disabled={busyId !== null}
                onClick={() => run(s.id, () => api(`/api/account/sessions/${s.id}`, { method: 'DELETE' }), 'Session signed out.')}
                className={ghostBtn}
              >
                {busyId === s.id ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <LogOut className="w-3.5 h-3.5" />} Sign out
              </button>
            )}
          </li>
        ))}
        {sessions.length === 0 && <li className="text-xs text-neutral-500">No tracked sessions yet. Sign out and back in to start tracking this device.</li>}
      </ul>
      {sessions.some((s) => !s.current) && (
        <button
          disabled={busyId !== null}
          onClick={() => run('all', () => api('/api/account/sessions/revoke-others', { method: 'POST' }), 'Signed out everywhere else.')}
          className={`${ghostBtn} mt-3`}
        >
          {busyId === 'all' && <Loader2 className="w-3.5 h-3.5 animate-spin" />} Sign out all other devices
        </button>
      )}
      <NoticeBar notice={notice} />
    </Card>
  );
}

function DeleteCard({ account }: { account: Account }) {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState<Notice | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setNotice(null);
    try {
      await api('/api/account/delete', post({ confirm_email: email, password: account.has_password ? password : null }));
      router.replace('/sign-in');
    } catch (err) {
      setNotice({ type: 'error', text: errMsg(err) });
      setBusy(false);
    }
  };

  return (
    <Card danger title="Delete account" hint="Permanently removes your documents, chats, shared links and account. This cannot be undone.">
      <form onSubmit={submit} className="space-y-3">
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder={`Type ${account.email} to confirm`} className={inputCls} />
        {account.has_password && (
          <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Password" className={inputCls} />
        )}
        <button
          type="submit"
          disabled={busy || !email || (account.has_password && !password)}
          className={`${primaryBtn} bg-red-600 hover:bg-red-700`}
        >
          {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />} Delete my account
        </button>
      </form>
      <NoticeBar notice={notice} />
    </Card>
  );
}

export default function SettingsPage() {
  const router = useRouter();
  const [account, setAccount] = useState<Account | null>(null);
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api<Account>('/api/account'), api<SessionInfo[]>('/api/account/sessions')])
      .then(([acc, list]) => {
        if (cancelled) return;
        setAccount(acc);
        setSessions(list);
        setError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof SessionExpiredError) router.replace('/sign-in');
        else setError(errMsg(err));
      });
    return () => {
      cancelled = true;
    };
  }, [tick, router]);

  const reload = () => setTick((t) => t + 1);

  return (
    <main className="flex-1 overflow-y-auto p-4 md:p-8">
      <div className="max-w-2xl mx-auto space-y-4 md:space-y-6">
        <div>
          <Link href="/" className="inline-flex items-center gap-1.5 text-xs text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200">
            <ArrowLeft className="w-3.5 h-3.5" /> Back to app
          </Link>
          <h1 className="mt-2 text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-100">Account settings</h1>
          {account && (
            <p className="text-xs md:text-sm text-neutral-500 mt-1">
              {account.username} · {account.email}
            </p>
          )}
        </div>

        {error && <div className="p-3 rounded-lg text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">{error}</div>}
        {!account && !error && (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-neutral-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        )}

        {account && (
          <>
            <PasswordCard hasPassword={account.has_password} onChanged={reload} />
            <SessionsCard sessions={sessions} reload={reload} />
            <DeleteCard account={account} />
          </>
        )}
      </div>
    </main>
  );
}
