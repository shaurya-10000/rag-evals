import type { ReactNode } from 'react';
import { Bot } from 'lucide-react';

export const labelClass =
  'block text-xs font-semibold text-neutral-600 dark:text-neutral-400 uppercase tracking-wider mb-2';
export const inputClass =
  'w-full bg-neutral-50 dark:bg-neutral-950 border border-neutral-200 dark:border-neutral-800 rounded-xl py-3 pl-11 pr-4 text-sm text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-emerald-500/50 focus:border-emerald-500 transition-all';
export const primaryButtonClass =
  'w-full flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white py-3 rounded-xl font-medium transition-all disabled:opacity-50 shadow-lg shadow-emerald-900/20';
export const errorClass =
  'p-3 rounded-lg text-xs text-center bg-red-500/10 text-red-400 border border-red-500/20';
export const noticeClass =
  'p-3 rounded-lg text-xs text-center bg-emerald-500/10 text-emerald-400 border border-emerald-500/20';
export const linkClass = 'text-emerald-400 hover:text-emerald-300';

export default function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-center min-h-screen p-4 bg-neutral-50 dark:bg-neutral-950">
      <div className="w-full max-w-md p-8 bg-white dark:bg-neutral-900/50 border border-neutral-200 dark:border-neutral-800 rounded-2xl backdrop-blur-md">
        <div className="flex items-center justify-center gap-3 mb-8">
          <div className="w-10 h-10 bg-emerald-500/10 rounded-lg flex items-center justify-center border border-emerald-500/20">
            <Bot className="w-6 h-6 text-emerald-400" />
          </div>
          <h1 className="text-2xl font-bold text-neutral-900 dark:text-neutral-100">{title}</h1>
        </div>
        {children}
      </div>
    </div>
  );
}
