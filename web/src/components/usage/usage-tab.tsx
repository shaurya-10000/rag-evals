'use client';

import { useEffect, useState } from 'react';
import { FileText, Layers, Loader2, MessageSquare, ThumbsUp } from 'lucide-react';
import type { Usage } from '@/lib/usage-types';
import { ActivityChart } from './activity-chart';
import { StatCard } from './stat-card';

type State =
  | { status: 'loading' }
  | { status: 'ready'; usage: Usage }
  | { status: 'error'; message: string };

const number = (value: number) => value.toLocaleString();

const percent = (part: number, total: number) => (total > 0 ? `${Math.round((part / total) * 100)}%` : 'n/a');

function formatSize(characters: number): string {
  if (characters >= 1_000_000) return `${(characters / 1_000_000).toFixed(1)}M characters`;
  if (characters >= 1_000) return `${Math.round(characters / 1_000)}k characters`;
  return `${characters} characters`;
}

export function UsageTab() {
  const [state, setState] = useState<State>({ status: 'loading' });

  useEffect(() => {
    let cancelled = false;
    fetch('/api/usage', { cache: 'no-store' })
      .then(async (res): Promise<State> => {
        const data = (await res.json().catch(() => null)) as (Usage & { error?: string }) | null;
        if (!res.ok || !data || typeof data.documents !== 'number') {
          return { status: 'error', message: data?.error || `Request failed (${res.status})` };
        }
        return { status: 'ready', usage: data };
      })
      .then((next) => {
        if (!cancelled) setState(next);
      })
      .catch(() => {
        if (!cancelled) setState({ status: 'error', message: 'Could not load your usage.' });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex-1 overflow-y-auto p-4 md:p-8 animate-in fade-in duration-300">
      <div className="max-w-4xl mx-auto space-y-6 md:space-y-8">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-neutral-900 dark:text-neutral-100">Usage</h2>
          <p className="text-xs md:text-sm text-neutral-500 mt-1">What is in your knowledge base and how it is being used.</p>
        </div>

        {state.status === 'loading' && (
          <div className="flex items-center justify-center gap-2 py-16 text-sm text-neutral-500">
            <Loader2 className="w-4 h-4 animate-spin" /> Loading...
          </div>
        )}

        {state.status === 'error' && (
          <div className="p-3 rounded-lg text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
            {state.message}
          </div>
        )}

        {state.status === 'ready' && <UsageReport usage={state.usage} />}
      </div>
    </div>
  );
}

function UsageReport({ usage }: { usage: Usage }) {
  const rated = usage.feedback_up + usage.feedback_down;
  const { imports, limits } = usage;

  return (
    <>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Documents"
          value={number(usage.documents)}
          hint={`${number(usage.chunks)} passages, ${formatSize(usage.characters)}`}
          icon={<FileText className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Chats"
          value={number(usage.conversations)}
          hint={`${number(usage.questions)} questions asked`}
          icon={<MessageSquare className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Answers refused"
          value={percent(usage.refused_answers, usage.answers)}
          hint={`${number(usage.refused_answers)} of ${number(usage.answers)} found nothing relevant`}
          icon={<Layers className="w-3.5 h-3.5" />}
        />
        <StatCard
          label="Helpful answers"
          value={percent(usage.feedback_up, rated)}
          hint={`${number(usage.feedback_up)} up, ${number(usage.feedback_down)} down`}
          icon={<ThumbsUp className="w-3.5 h-3.5" />}
        />
      </div>

      <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/50 p-4 md:p-5 shadow-sm">
        <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-4">Questions per day</h3>
        <ActivityChart data={usage.daily_questions} />
      </section>

      <div className="grid md:grid-cols-2 gap-3">
        <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/50 p-4 md:p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Imports, last 30 days</h3>
          <dl className="space-y-2 text-xs md:text-sm">
            <div className="flex justify-between"><dt className="text-neutral-500">Succeeded</dt><dd>{number(imports.succeeded)}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">Failed</dt><dd>{number(imports.failed)}</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">In progress</dt><dd>{number(imports.active)}</dd></div>
          </dl>
        </section>

        <section className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/50 p-4 md:p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 mb-3">Limits</h3>
          <dl className="space-y-2 text-xs md:text-sm">
            <div className="flex justify-between"><dt className="text-neutral-500">Questions</dt><dd>{limits.questions_per_minute} per minute</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">Upload size</dt><dd>{limits.max_upload_mb} MB</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">Document text</dt><dd>{number(limits.max_document_chars)} characters</dd></div>
            <div className="flex justify-between"><dt className="text-neutral-500">Imports at once</dt><dd>{limits.max_active_imports}</dd></div>
          </dl>
        </section>
      </div>
    </>
  );
}
