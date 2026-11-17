'use client';

import { useEffect, useState } from 'react';
import { Check, Copy, Link2, Loader2, X } from 'lucide-react';
import type { Conversation, ShareInfo } from '@/lib/chat-types';
import { createShare, deleteShare, getShare } from '@/lib/conversations-api';

type Props = { conversation: Conversation; onClose: () => void };

const ghostBtn =
  'flex items-center gap-1.5 px-3 py-2 text-xs font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-300 dark:hover:text-white bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 rounded-lg transition-colors disabled:opacity-50';
const primaryBtn =
  'flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-white text-xs font-medium shadow-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed';

const messageOf = (err: unknown) => (err instanceof Error ? err.message : 'Something went wrong');

export function ShareDialog({ conversation, onClose }: Props) {
  const [share, setShare] = useState<ShareInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getShare(conversation.id)
      .then((info) => {
        if (!cancelled) setShare(info);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [conversation.id]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const run = async (action: () => Promise<ShareInfo>) => {
    setBusy(true);
    setError(null);
    try {
      setShare(await action());
    } catch (err) {
      setError(messageOf(err));
    } finally {
      setBusy(false);
    }
  };

  const link = share?.shared && share.token ? `${window.location.origin}/s/${share.token}` : null;

  const copy = async () => {
    if (!link) return;
    await navigator.clipboard.writeText(link);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Share chat"
      className="fixed inset-0 z-[90] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-md bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-5 py-4 border-b border-neutral-200 dark:border-neutral-800">
          <Link2 className="w-4 h-4 text-accent-500" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100">Share chat</p>
            <p className="text-xs text-neutral-500 truncate">{conversation.title}</p>
          </div>
          <button onClick={onClose} className="p-1 rounded-md text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800" aria-label="Close">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <p className="text-xs leading-relaxed text-neutral-500">
            Anyone with the link can read this conversation, including the document passages it cites, without
            signing in. It is a snapshot: new messages only appear after you update it.
          </p>

          {loading ? (
            <div className="flex items-center justify-center gap-2 py-4 text-xs text-neutral-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading...
            </div>
          ) : link ? (
            <>
              <div className="flex items-center gap-2">
                <input
                  readOnly
                  value={link}
                  onFocus={(e) => e.currentTarget.select()}
                  className="flex-1 min-w-0 bg-neutral-50 dark:bg-neutral-950 border border-neutral-300 dark:border-neutral-800 rounded-lg py-2 px-3 text-xs text-neutral-900 dark:text-neutral-100"
                />
                <button onClick={copy} className={ghostBtn}>
                  {copied ? <Check className="w-3.5 h-3.5 text-accent-500" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'Copied' : 'Copy'}
                </button>
              </div>
              <div className="flex items-center justify-between gap-2">
                <button onClick={() => run(() => createShare(conversation.id))} disabled={busy} className={ghostBtn}>
                  Update shared copy
                </button>
                <button
                  onClick={() => run(() => deleteShare(conversation.id))}
                  disabled={busy}
                  className="px-3 py-2 text-xs font-medium text-red-500 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-lg transition-colors disabled:opacity-50"
                >
                  Stop sharing
                </button>
              </div>
            </>
          ) : (
            <button
              onClick={() => run(() => createShare(conversation.id))}
              disabled={busy}
              className={`${primaryBtn} w-full`}
              style={{ backgroundColor: 'var(--accent-600)' }}
            >
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Link2 className="w-4 h-4" />}
              Create link
            </button>
          )}

          {error && (
            <div className="p-2 rounded-lg text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
