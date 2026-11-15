'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { AlertTriangle, ArrowDownToLine, FileText, Loader2, Pencil, X } from 'lucide-react';
import type { Source } from '@/lib/chat-types';
import { locatePassage, tidyPassage } from '@/lib/passage';

type Props = {
  documentId: string;
  source: Source;
  sourceNumber: number;
  onClose: () => void;
  onEdit: (documentId: string) => void;
};

type DocState =
  | { status: 'loading' }
  | { status: 'ready'; title: string; content: string }
  | { status: 'missing' }
  | { status: 'error'; message: string };

const ghostBtn =
  'flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 rounded-md transition-colors';

function Notice({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex items-start gap-2 p-3 rounded-xl text-xs bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function SavedPassage({ text }: { text: string }) {
  return (
    <div className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-950 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500 mb-1.5">Cited passage</p>
      <p className="text-xs leading-relaxed text-neutral-700 dark:text-neutral-300 whitespace-pre-wrap">
        {tidyPassage(text)}
      </p>
    </div>
  );
}

export function DocumentViewer({ documentId, source, sourceNumber, onClose, onEdit }: Props) {
  const [doc, setDoc] = useState<DocState>({ status: 'loading' });
  const markRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`/api/documents/${encodeURIComponent(documentId)}`, { cache: 'no-store' })
      .then(async (res): Promise<DocState> => {
        if (res.status === 404) return { status: 'missing' };
        const data = (await res.json().catch(() => null)) as
          | { title?: string; content?: string; error?: string }
          | null;
        if (!res.ok || !data || typeof data.content !== 'string') {
          return { status: 'error', message: data?.error || `Request failed (${res.status})` };
        }
        return { status: 'ready', title: data.title ?? source.document_title ?? 'Document', content: data.content };
      })
      .then((next) => {
        if (!cancelled) setDoc(next);
      })
      .catch(() => {
        if (!cancelled) setDoc({ status: 'error', message: 'Could not load the document.' });
      });
    return () => {
      cancelled = true;
    };
  }, [documentId, source.document_title]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose]);

  const range = useMemo(
    () => (doc.status === 'ready' ? locatePassage(doc.content, source.content) : null),
    [doc, source.content]
  );

  useEffect(() => {
    if (doc.status === 'ready' && range) markRef.current?.scrollIntoView({ block: 'center' });
  }, [doc, range]);

  const title = doc.status === 'ready' ? doc.title : source.document_title || 'Document';

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`Source ${sourceNumber}: ${title}`}
      className="fixed inset-0 z-[90] flex items-center justify-center p-3 md:p-6 bg-black/50 backdrop-blur-sm"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="w-full max-w-3xl max-h-[92dvh] flex flex-col bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center gap-3 px-4 md:px-5 py-3 md:py-4 border-b border-neutral-200 dark:border-neutral-800">
          <div className="w-8 h-8 rounded-xl bg-accent-500/10 border border-accent-500/20 flex items-center justify-center shrink-0">
            <FileText className="w-4 h-4 text-accent-500" />
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-neutral-900 dark:text-neutral-100 truncate">{title}</p>
            <p className="text-[10px] md:text-xs text-neutral-500">Source {sourceNumber}</p>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-md text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
            aria-label="Close"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 md:p-5 space-y-4">
          {doc.status === 'loading' && (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-neutral-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading document...
            </div>
          )}

          {doc.status === 'error' && (
            <div className="p-3 rounded-lg text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
              {doc.message}
            </div>
          )}

          {doc.status === 'missing' && (
            <>
              <Notice>
                <p className="font-medium">This document has been deleted.</p>
                <p>Here is the passage that was cited when the answer was written.</p>
              </Notice>
              <SavedPassage text={source.content} />
            </>
          )}

          {doc.status === 'ready' && (
            <>
              {!range && (
                <>
                  <Notice>
                    <p className="font-medium">Couldn&apos;t find this passage in the current text.</p>
                    <p>The document was probably edited after this answer. Showing the full document instead.</p>
                  </Notice>
                  <SavedPassage text={source.content} />
                </>
              )}
              <p className="text-sm leading-7 text-neutral-800 dark:text-neutral-200 whitespace-pre-wrap break-words">
                {range ? (
                  <>
                    {doc.content.slice(0, range.start)}
                    <mark
                      ref={markRef}
                      className="bg-accent-500/25 text-inherit rounded px-0.5 py-0.5 scroll-mt-24"
                    >
                      {doc.content.slice(range.start, range.end)}
                    </mark>
                    {doc.content.slice(range.end)}
                  </>
                ) : (
                  doc.content
                )}
              </p>
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 px-4 md:px-5 py-3 border-t border-neutral-200 dark:border-neutral-800">
          <div className="flex items-center gap-2">
            {doc.status === 'ready' && range && (
              <button onClick={() => markRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })} className={ghostBtn}>
                <ArrowDownToLine className="w-3.5 h-3.5" /> Jump to passage
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
            {doc.status === 'ready' && (
              <button onClick={() => onEdit(documentId)} className={ghostBtn}>
                <Pencil className="w-3.5 h-3.5" /> Edit document
              </button>
            )}
            <button onClick={onClose} className={ghostBtn}>
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
