'use client';

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { X } from 'lucide-react';
import type { Source } from '@/lib/chat-types';
import { SourceCard } from './source-card';

type Props = {
  sources: Source[];
  activeNumber: number;
  onClose: () => void;
  onViewDocument: (source: Source, number: number) => void;
};

export function SourcePanel({ sources, activeNumber, onClose, onViewDocument }: Props) {
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
      <div className="flex items-start justify-between px-5 pt-4 pb-2">
        <div>
          <p className="font-semibold text-sm text-neutral-900 dark:text-neutral-100">Sources</p>
          <p className="text-[10px] md:text-xs text-neutral-500 mt-0.5">
            {sources.length} passage{sources.length === 1 ? '' : 's'} used for this answer
          </p>
        </div>
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
            <SourceCard
              key={source.id}
              source={source}
              number={number}
              active={isActive}
              cardRef={isActive ? activeRef : undefined}
              onView={() => onViewDocument(source, number)}
            />
          );
        })}
      </div>
    </motion.aside>
  );
}
