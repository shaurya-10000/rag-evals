'use client';

import { Sparkles } from 'lucide-react';

const SUGGESTIONS = [
  { title: 'Summarize documents', hint: 'Get a quick TL;DR', prompt: 'Summarize the key points of my documents.' },
  { title: 'Find specific policies', hint: 'Extract rules and guidelines', prompt: 'What are the main policies mentioned?' },
];

export function EmptyState({ onPick }: { onPick: (prompt: string) => void }) {
  return (
    <div className="flex flex-col items-center justify-center flex-1 text-center space-y-6 md:space-y-8 animate-in fade-in zoom-in-95 duration-500 mt-10 md:mt-0">
      <div className="space-y-2 md:space-y-3">
        <div
          className="w-16 h-16 md:w-20 md:h-20 rounded-3xl flex items-center justify-center mx-auto shadow-2xl"
          style={{
            background: 'linear-gradient(135deg, var(--accent-500) 0%, transparent 100%)',
            border: '1px solid var(--accent-500)',
            boxShadow: '0 0 30px -5px var(--accent-500)',
          }}
        >
          <Sparkles className="w-8 h-8 md:w-10 md:h-10" style={{ color: 'var(--accent-500)' }} />
        </div>
        <h2 className="text-2xl md:text-3xl font-bold text-neutral-900 dark:text-neutral-100 tracking-tight mt-4">
          How can I help you today?
        </h2>
        <p className="text-neutral-500 text-xs md:text-sm">Ask anything about your ingested documents.</p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 md:gap-3 w-full max-w-2xl px-2">
        {SUGGESTIONS.map((s) => (
          <button
            key={s.title}
            onClick={() => onPick(s.prompt)}
            className="p-3 md:p-4 bg-white dark:bg-neutral-900/50 hover:bg-neutral-50 dark:hover:bg-neutral-800 border border-neutral-200 dark:border-neutral-800 rounded-xl text-left transition-all group shadow-sm"
          >
            <p className="text-xs md:text-sm font-medium text-neutral-900 dark:text-neutral-200 group-hover:text-black dark:group-hover:text-white">
              {s.title}
            </p>
            <p className="text-[10px] md:text-xs text-neutral-500 dark:text-neutral-400 mt-1">{s.hint}</p>
          </button>
        ))}
      </div>
    </div>
  );
}
