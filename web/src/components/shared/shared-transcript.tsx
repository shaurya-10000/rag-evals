'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Layers, User } from 'lucide-react';
import { AssistantMarkdown } from '@/components/chat/assistant-markdown';
import type { SharedChat, SharedMessage } from '@/lib/chat-types';

type SourceListProps = {
  message: SharedMessage;
  messageIndex: number;
  open: ReadonlySet<string>;
  onToggle: (key: string) => void;
};

const keyOf = (messageIndex: number, number: number) => `${messageIndex}:${number}`;

function SourceList({ message, messageIndex, open, onToggle }: SourceListProps) {
  if (message.sources.length === 0) return null;
  return (
    <ol className="mt-3 space-y-1.5">
      {message.sources.map((source, index) => {
        const number = index + 1;
        const key = keyOf(messageIndex, number);
        const expanded = open.has(key);
        return (
          <li
            key={key}
            id={`source-${key}`}
            className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50"
          >
            <button
              type="button"
              onClick={() => onToggle(key)}
              aria-expanded={expanded}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs text-neutral-700 dark:text-neutral-300"
            >
              <span className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 rounded-md bg-accent-500/15 text-accent-600 dark:text-accent-400 text-[11px] font-semibold">
                {number}
              </span>
              <span className="truncate font-medium">{source.document_title || 'Source'}</span>
            </button>
            {expanded && (
              <p className="px-3 pb-3 text-xs leading-relaxed text-neutral-600 dark:text-neutral-400 whitespace-pre-wrap">
                {source.content}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}

export function SharedTranscript({ chat }: { chat: SharedChat }) {
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());

  const toggle = (key: string) =>
    setOpen((current) => {
      const next = new Set(current);
      if (!next.delete(key)) next.add(key);
      return next;
    });

  const reveal = (messageIndex: number, number: number) => {
    const key = keyOf(messageIndex, number);
    setOpen((current) => new Set(current).add(key));
    window.requestAnimationFrame(() =>
      document.getElementById(`source-${key}`)?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
    );
  };

  return (
    <div className="min-h-[100dvh] bg-background text-foreground">
      <header className="border-b border-neutral-200 dark:border-neutral-800/50">
        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">
          <div
            className="w-8 h-8 rounded-xl flex items-center justify-center shadow-lg shrink-0"
            style={{ background: 'linear-gradient(to bottom right, var(--accent-500), var(--accent-600))' }}
          >
            <Layers className="w-4 h-4 text-white" />
          </div>
          <div className="min-w-0 flex-1">
            <h1 className="text-sm md:text-base font-bold truncate">{chat.title}</h1>
            <p className="text-[10px] md:text-xs text-neutral-500">
              Read-only snapshot, shared{' '}
              <time dateTime={chat.shared_at} suppressHydrationWarning>
                {new Date(chat.shared_at).toLocaleDateString()}
              </time>
            </p>
          </div>
          <Link
            href="/sign-up"
            className="px-3 py-1.5 rounded-lg text-white text-xs font-medium shrink-0"
            style={{ backgroundColor: 'var(--accent-600)' }}
          >
            Try RAG Evals
          </Link>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 py-6 md:py-8 space-y-5 md:space-y-6">
        {chat.messages.map((message, index) =>
          message.role === 'user' ? (
            <div key={index} className="flex gap-2 md:gap-4 justify-end">
              <div className="max-w-[85%] bg-accent-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 md:px-5 md:py-3 shadow-md">
                <p className="text-xs md:text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
              </div>
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-3 h-3 md:w-5 md:h-5 text-neutral-600 dark:text-neutral-400" />
              </div>
            </div>
          ) : (
            <div key={index} className="flex gap-2 md:gap-4">
              <div className="w-6 h-6 md:w-8 md:h-8 rounded-full bg-accent-500/10 border border-accent-500/20 flex items-center justify-center shrink-0 mt-0.5">
                <Layers className="w-3 h-3 md:w-4 md:h-4 text-accent-500" />
              </div>
              <div className="min-w-0 max-w-[85%]">
                <div className="prose dark:prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-table:w-full">
                  <AssistantMarkdown
                    content={message.content}
                    sourceCount={message.sources.length}
                    onCite={(number) => reveal(index, number)}
                  />
                </div>
                <SourceList message={message} messageIndex={index} open={open} onToggle={toggle} />
              </div>
            </div>
          )
        )}
      </main>

      <footer className="max-w-3xl mx-auto px-4 pb-10 text-center text-[10px] md:text-xs text-neutral-500">
        This conversation was shared from RAG Evals. Answers can contain mistakes.
      </footer>
    </div>
  );
}
