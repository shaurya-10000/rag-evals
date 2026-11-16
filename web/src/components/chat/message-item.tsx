'use client';

import { memo, useCallback } from 'react';
import { Check, Copy, Database, Info, Layers, Loader2, Search, Square, User, Volume2 } from 'lucide-react';
import type { ChatMessage, Source } from '@/lib/chat-types';
import { AssistantMarkdown } from './assistant-markdown';

type Props = {
  message: ChatMessage;
  messageKey: string;
  copied: boolean;
  speaking: boolean;
  onCopy: (text: string, key: string) => void;
  onSpeak: (text: string, key: string) => void;
  onOpenSource: (sources: Source[], sourceNumber: number) => void;
};

const EMPTY_SOURCES: Source[] = [];

const actionBtn =
  'flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-neutral-500 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-900 dark:hover:bg-neutral-800 rounded-md transition-colors';

export const MessageItem = memo(function MessageItem({
  message,
  messageKey,
  copied,
  speaking,
  onCopy,
  onSpeak,
  onOpenSource,
}: Props) {
  const isUser = message.role === 'user';
  const sources = message.sources ?? EMPTY_SOURCES;
  const isThinking = !isUser && message.content === '' && message.isStreaming;

  const handleCite = useCallback(
    (sourceNumber: number) => onOpenSource(sources, sourceNumber),
    [onOpenSource, sources]
  );

  return (
    <div className={`flex gap-2 md:gap-4 ${isUser ? 'justify-end' : 'justify-start'} animate-in fade-in slide-in-from-bottom-2 duration-300`}>
      {!isUser && (
        <div className="w-6 h-6 md:w-8 md:h-8 rounded-full bg-accent-500/10 border border-accent-500/20 flex items-center justify-center shrink-0 mt-0.5">
          <Layers className="w-3 h-3 md:w-4 md:h-4 text-accent-500" />
        </div>
      )}
      <div
        className={`max-w-[85%] ${
          isUser
            ? 'bg-accent-600 text-white rounded-2xl rounded-tr-sm px-4 py-2 md:px-5 md:py-3 shadow-md'
            : 'bg-transparent text-neutral-800 dark:text-neutral-200'
        }`}
      >
        {isUser ? (
          <p className="text-xs md:text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="group relative">
            <div className="prose dark:prose-invert prose-sm max-w-none prose-p:leading-relaxed prose-pre:bg-neutral-100 dark:prose-pre:bg-neutral-950 prose-pre:border prose-pre:border-neutral-200 dark:prose-pre:border-neutral-800 prose-table:w-full prose-table:border-collapse">
              {isThinking ? (
                <div className="flex items-center gap-2 h-6 text-sm text-accent-500 font-medium">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span className="animate-pulse">Searching knowledge base...</span>
                </div>
              ) : (
                <>
                  <AssistantMarkdown content={message.content} sourceCount={sources.length} onCite={handleCite} />
                  {message.isStreaming && (
                    <span className="inline-block w-1.5 h-4 ml-1 bg-accent-500 animate-pulse align-middle" />
                  )}
                </>
              )}
            </div>

            {!message.isStreaming && message.refused && (
              <p className="mt-2 flex items-start gap-1.5 text-[10px] md:text-xs text-amber-600 dark:text-amber-400">
                <Info className="w-3.5 h-3.5 shrink-0 mt-px" />
                <span>
                  Nothing relevant was found in your documents for this question. Try adding documents or
                  searching in a different collection.
                </span>
              </p>
            )}

            {!message.isStreaming && message.rewrittenQuery && (
              <p className="mt-2 flex items-start gap-1.5 text-[10px] md:text-xs text-neutral-500">
                <Search className="w-3.5 h-3.5 shrink-0 mt-px" />
                <span>
                  Searched for: <span className="italic">{message.rewrittenQuery}</span>
                </span>
              </p>
            )}

            {!message.isStreaming && message.content && (
              <div className="mt-2 flex items-center gap-2 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-opacity duration-200">
                <button onClick={() => onCopy(message.content, messageKey)} className={actionBtn} title="Copy text">
                  {copied ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-accent-500" /> Copied
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" /> Copy
                    </>
                  )}
                </button>
                <button onClick={() => onSpeak(message.content, messageKey)} className={actionBtn} title="Read aloud">
                  {speaking ? (
                    <>
                      <Square className="w-3.5 h-3.5 fill-current text-accent-500" /> Stop
                    </>
                  ) : (
                    <>
                      <Volume2 className="w-3.5 h-3.5" /> Read aloud
                    </>
                  )}
                </button>
              </div>
            )}

            {sources.length > 0 && (
              <div className="mt-3 flex flex-wrap items-center gap-1.5">
                <span className="flex items-center gap-1.5 mr-1 text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
                  <Database className="w-3.5 h-3.5 text-accent-500" /> Sources
                </span>
                {sources.map((source, index) => (
                  <button
                    key={source.id}
                    type="button"
                    onClick={() => onOpenSource(sources, index + 1)}
                    title={source.document_title ?? undefined}
                    className="inline-flex items-center gap-1.5 max-w-[14rem] px-2 py-1 rounded-lg border border-neutral-200 dark:border-neutral-800 bg-neutral-50 dark:bg-neutral-900/50 hover:bg-neutral-100 dark:hover:bg-neutral-800 text-[10px] md:text-xs text-neutral-600 dark:text-neutral-300 transition-colors"
                  >
                    <span className="font-bold text-accent-600">{index + 1}</span>
                    <span className="truncate">{source.document_title || 'Source'}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {isUser && (
        <div className="w-6 h-6 md:w-8 md:h-8 rounded-full bg-neutral-200 dark:bg-neutral-800 flex items-center justify-center shrink-0 mt-0.5">
          <User className="w-3 h-3 md:w-5 md:h-5 text-neutral-600 dark:text-neutral-400" />
        </div>
      )}
    </div>
  );
});
