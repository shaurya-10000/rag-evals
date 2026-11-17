import type { ReactNode } from 'react';

type Props = { label: string; value: string; hint?: string; icon: ReactNode };

export function StatCard({ label, value, hint, icon }: Props) {
  return (
    <div className="rounded-2xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/50 p-4 shadow-sm">
      <div className="flex items-center gap-2 text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
        <span className="text-accent-500">{icon}</span> {label}
      </div>
      <p className="mt-2 text-2xl font-bold text-neutral-900 dark:text-neutral-100">{value}</p>
      {hint && <p className="mt-1 text-[10px] md:text-xs text-neutral-500">{hint}</p>}
    </div>
  );
}
