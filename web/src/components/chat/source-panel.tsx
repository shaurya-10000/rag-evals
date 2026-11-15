'use client';

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ExternalLink, FileText, X } from 'lucide-react';
import type { Source } from '@/lib/chat-types';

type Props = {
  sources: Source[];
  activeNumber: number;
  onClose: () => void;
  onOpenDocument: (documentId: string) => void;
};

const passageLabel = (source: Source) => {
  const index = source.metadata?.index;
  return typeof index === 'number' ? `Passage ${index + 1}` : 'Passage';
};

export function SourcePanel({ sources, activeNumber, onClose, onOpenDocument }: Props) {
  const activeRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    activeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeNumber]);

  return (
    <motion.aside
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      aria-label="Sources"
      className="fixed inset-y-3 right-3 z-[70] flex w-[26rem] max-w-[calc(100vw-1.5rem)] flex-col rounded-[2rem] border border-neutral-200 dark:border-white/[0.08] bg-white dark:bg-[#0a0a0a] shadow-2xl overflow-hidden"
    >
      <div className="flex items-center justify-between px-5 pt-4 pb-2">
        <span className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">Sources</span>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg text-neutral-500 hover:bg-neutral-100 dark:hover:bg-white/[0.06] transition-colors"
          title="Close"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3">
        {sources.map((source, index) => {
          const number = index + 1;
          const isActive = number === activeNumber;
          return (
            <article
              key={source.id}
              ref={isActive ? activeRef : undefined}
              className={`rounded-2xl border p-3 md:p-4 transition-colors ${
                isActive
                  ? 'border-accent-500 bg-accent-500/5'
                  : 'border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50'
              }`}
            >
              <div className="flex items-start gap-2">
                <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-md bg-accent-500/15 text-accent-600 dark:text-accent-400 text-[11px] font-semibold shrink-0">
                  {number}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-xs md:text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">
                    {source.document_title || 'Source'}
                  </p>
                  <p className="text-[10px] text-neutral-500 mt-0.5">{passageLabel(source)}</p>
                </div>
              </div>
              <p className="mt-3 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
                {source.content}
              </p>
              {source.document_id && (
                <button
                  onClick={() => onOpenDocument(source.document_id as string)}
                  className="mt-3 flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-md transition-colors"
                >
                  <FileText className="w-3.5 h-3.5" /> Open document <ExternalLink className="w-3 h-3" />
                </button>
              )}
            </article>
          );
        })}
      </div>
    </motion.aside>
  );
}
