'use client';

import { Loader2, Pin, Search, X } from 'lucide-react';
import type { SearchHit } from '@/lib/chat-types';

type BoxProps = { value: string; onChange: (value: string) => void };

export function SearchBox({ value, onChange }: BoxProps) {
  return (
    <div className="px-4 pb-2">
      <div className="relative">
        <Search className="w-3.5 h-3.5 text-neutral-500 absolute left-3 top-1/2 -translate-y-1/2" />
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === 'Escape' && onChange('')}
          maxLength={100}
          placeholder="Search chats..."
          aria-label="Search chats"
          className="w-full bg-neutral-50 dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-xl py-1.5 pl-8 pr-8 text-xs text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50"
        />
        {value && (
          <button
            onClick={() => onChange('')}
            aria-label="Clear search"
            className="absolute right-2 top-1/2 -translate-y-1/2 p-0.5 rounded text-neutral-500 hover:text-neutral-900 dark:hover:text-neutral-200"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

type ResultsProps = {
  hits: SearchHit[];
  loading: boolean;
  error: string | null;
  onSelect: (id: string) => void;
};

export function SearchResults({ hits, loading, error, onSelect }: ResultsProps) {
  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 text-xs text-neutral-500 py-4 mt-4">
        <Loader2 className="w-3.5 h-3.5 animate-spin" /> Searching...
      </div>
    );
  }
  if (error) {
    return <div className="mx-1 p-2 rounded-lg text-[10px] text-center bg-red-500/10 text-red-500 border border-red-500/20">{error}</div>;
  }
  if (hits.length === 0) {
    return <div className="text-xs text-center text-neutral-500 py-4 mt-4">No chats match.</div>;
  }
  return (
    <>
      {hits.map((hit) => (
        <button
          key={hit.id}
          onClick={() => onSelect(hit.id)}
          className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-neutral-100 dark:hover:bg-white/[0.04] transition-colors"
        >
          <span className="flex items-center gap-2 text-sm text-neutral-800 dark:text-neutral-100">
            {hit.pinned && <Pin className="w-3 h-3 text-accent-500 shrink-0" />}
            <span className="truncate">{hit.title}</span>
          </span>
          {hit.snippet && <span className="block mt-0.5 text-[11px] text-neutral-500 line-clamp-2">{hit.snippet}</span>}
        </button>
      ))}
    </>
  );
}
