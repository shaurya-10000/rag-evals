'use client';

import { Send } from 'lucide-react';
import type { CollectionInfo } from '@/components/documents-tab';

type Props = {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  collections: CollectionInfo[];
  scopeCollectionId: string;
  onScopeChange: (id: string) => void;
};

export function Composer({ value, onChange, onSubmit, disabled, collections, scopeCollectionId, onScopeChange }: Props) {
  const canSend = !disabled && value.trim().length > 0;
  const submit = () => {
    if (canSend) onSubmit();
  };

  return (
    <footer className="p-2 md:p-4 border-t border-neutral-200 dark:border-neutral-800/50 bg-transparent shrink-0">
      <div className="w-full max-w-4xl mx-auto">
        {collections.length > 0 && (
          <div className="flex items-center gap-2 mb-2 px-1">
            <span className="text-[10px] md:text-xs font-medium text-neutral-500">Search in</span>
            <select
              value={scopeCollectionId}
              onChange={(e) => onScopeChange(e.target.value)}
              className="bg-neutral-50 dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-lg py-1 px-2 text-[10px] md:text-xs text-neutral-900 dark:text-neutral-100 focus:outline-none focus:ring-2 focus:ring-accent-500/50 max-w-[60%]"
            >
              <option value="">All documents</option>
              {collections.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="relative flex items-end gap-2 bg-white dark:bg-neutral-900 border border-neutral-300 dark:border-neutral-700 rounded-2xl p-1.5 md:p-2 focus-within:ring-2 focus-within:ring-accent-500/50 focus-within:border-accent-500 transition-all shadow-sm"
        >
          <textarea
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Message RAG Evals..."
            rows={1}
            className="w-full max-h-32 bg-transparent text-xs md:text-sm text-neutral-900 dark:text-neutral-100 placeholder-neutral-500 px-2 md:px-3 py-1.5 md:py-2.5 resize-none focus:outline-none"
            style={{ minHeight: '36px', maxHeight: '120px' }}
          />
          <button
            type="submit"
            disabled={!canSend}
            className="p-1.5 md:p-2.5 mb-0.5 text-white rounded-xl transition-all disabled:opacity-50 disabled:bg-neutral-200 dark:disabled:bg-neutral-800 disabled:text-neutral-500 shrink-0 shadow-sm"
            style={{ backgroundColor: 'var(--accent-600)' }}
            aria-label="Send message"
          >
            <Send className="w-3.5 h-3.5 md:w-4 md:h-4" />
          </button>
        </form>
        <p className="text-center text-[9px] md:text-[10px] text-neutral-500 mt-1 md:mt-2">
          RAG Evals can make mistakes. Consider verifying important information.
        </p>
      </div>
    </footer>
  );
}
