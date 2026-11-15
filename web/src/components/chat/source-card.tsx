'use client';

import { useState, type Ref } from 'react';
import { ChevronDown, ChevronUp, FileSearch } from 'lucide-react';
import type { Source } from '@/lib/chat-types';
import { tidyPassage } from '@/lib/passage';

const CLAMP_THRESHOLD_CHARS = 420;

type Props = {
  source: Source;
  number: number;
  active: boolean;
  cardRef?: Ref<HTMLElement>;
  onView: () => void;
};

function passageLabel(source: Source): string | null {
  const index = source.metadata?.index;
  return typeof index === 'number' ? `Passage ${index + 1}` : null;
}

export function SourceCard({ source, number, active, cardRef, onView }: Props) {
  const [expanded, setExpanded] = useState(false);
  const text = tidyPassage(source.content);
  const isLong = text.length > CLAMP_THRESHOLD_CHARS;
  const deleted = source.document_available === false;
  const unknown = !source.document_id;
  const canView = !deleted && !unknown;
  const label = passageLabel(source);

  return (
    <article
      ref={cardRef}
      className={`rounded-2xl border p-3 md:p-4 transition-colors ${
        active
          ? 'border-accent-500 bg-accent-500/5'
          : 'border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50'
      }`}
    >
      <div className="flex items-start gap-2.5">
        <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 mt-0.5 rounded-md bg-accent-500/15 text-accent-600 dark:text-accent-400 text-[11px] font-semibold shrink-0">
          {number}
        </span>
        <div className="min-w-0 flex-1">
          <p className="text-xs md:text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">
            {source.document_title || 'Unknown document'}
          </p>
          <p className="text-[10px] md:text-xs text-neutral-500 mt-0.5">
            {[label, deleted ? 'Document deleted' : unknown ? 'Original document not found' : null]
              .filter(Boolean)
              .join(' · ') || 'Cited passage'}
          </p>
        </div>
      </div>

      <p
        className={`mt-3 text-xs leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap ${
          expanded ? '' : 'line-clamp-6'
        }`}
      >
        {text}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {canView && (
          <button
            onClick={onView}
            className="flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-white rounded-md transition-opacity hover:opacity-90"
            style={{ backgroundColor: 'var(--accent-600)' }}
          >
            <FileSearch className="w-3.5 h-3.5" /> View in document
          </button>
        )}
        {isLong && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="flex items-center gap-1 px-2 py-1.5 text-[10px] md:text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 transition-colors"
          >
            {expanded ? (
              <>
                <ChevronUp className="w-3.5 h-3.5" /> Show less
              </>
            ) : (
              <>
                <ChevronDown className="w-3.5 h-3.5" /> Show full passage
              </>
            )}
          </button>
        )}
      </div>
    </article>
  );
}
