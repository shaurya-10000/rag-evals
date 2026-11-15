'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import type { CollectionInfo } from '@/components/documents-tab';
import type { ChatMessage, Source } from '@/lib/chat-types';
import { Composer } from './composer';
import { EmptyState } from './empty-state';
import { MessageItem } from './message-item';
import { SourcePanel } from './source-panel';

type Props = {
  active: boolean;
  conversationId: string | null;
  messages: ChatMessage[];
  historyLoading: boolean;
  isStreaming: boolean;
  error: string | null;
  collections: CollectionInfo[];
  scopeCollectionId: string;
  onScopeChange: (id: string) => void;
  onSend: (text: string) => void;
  onOpenDocument: (documentId: string) => void;
};

type Citation = { conversationId: string | null; sources: Source[]; number: number };

export function ChatTab({
  active,
  conversationId,
  messages,
  historyLoading,
  isStreaming,
  error,
  collections,
  scopeCollectionId,
  onScopeChange,
  onSend,
  onOpenDocument,
}: Props) {
  const [input, setInput] = useState('');
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [speakingKey, setSpeakingKey] = useState<string | null>(null);
  const [citation, setCitation] = useState<Citation | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // A citation belongs to the conversation it was opened in.
  const panel = citation && citation.conversationId === conversationId ? citation : null;

  useEffect(() => {
    if (active) endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, active]);

  // Stop reading aloud when the conversation changes or the tab unmounts.
  useEffect(
    () => () => {
      window.speechSynthesis?.cancel();
    },
    [conversationId]
  );

  useEffect(() => {
    if (!panel) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setCitation(null);
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [panel]);

  const handleCopy = useCallback((text: string, key: string) => {
    void navigator.clipboard.writeText(text);
    setCopiedKey(key);
    window.setTimeout(() => setCopiedKey((current) => (current === key ? null : current)), 2000);
  }, []);

  const handleSpeak = useCallback(
    (text: string, key: string) => {
      const synth = window.speechSynthesis;
      if (!synth) return;
      if (speakingKey === key) {
        synth.cancel();
        setSpeakingKey(null);
        return;
      }
      synth.cancel();
      const clean = text.replace(/\[\d+(?:\s*,\s*\d+)*\]/g, '').replace(/[#*`_~]/g, '');
      const utterance = new SpeechSynthesisUtterance(clean);
      const savedVoice = window.localStorage.getItem('rag-evals-voice');
      if (savedVoice) {
        const voice = synth.getVoices().find((v) => v.name === savedVoice);
        if (voice) utterance.voice = voice;
      }
      const clear = () => setSpeakingKey((current) => (current === key ? null : current));
      utterance.onend = clear;
      utterance.onerror = clear;
      setSpeakingKey(key);
      synth.speak(utterance);
    },
    [speakingKey]
  );

  const handleOpenSource = useCallback(
    (sources: Source[], sourceNumber: number) => setCitation({ conversationId, sources, number: sourceNumber }),
    [conversationId]
  );

  const handleSubmit = () => {
    const text = input;
    setInput('');
    onSend(text);
  };

  const keyPrefix = conversationId ?? 'new';

  return (
    <div hidden={!active} className="flex-1 flex flex-col h-full animate-in fade-in duration-300">
      <div className="flex-1 overflow-y-auto w-full">
        <div className="max-w-4xl mx-auto p-3 sm:p-6 md:p-8 min-h-full flex flex-col">
          {historyLoading ? (
            <div className="flex flex-1 items-center justify-center gap-2 text-sm text-neutral-500">
              <Loader2 className="w-4 h-4 animate-spin" /> Loading conversation...
            </div>
          ) : messages.length === 0 ? (
            <EmptyState onPick={setInput} />
          ) : (
            <div className="space-y-4 md:space-y-6">
              {messages.map((message, i) => {
                const key = `${keyPrefix}:${i}`;
                return (
                  <MessageItem
                    key={message.id ?? key}
                    message={message}
                    messageKey={key}
                    copied={copiedKey === key}
                    speaking={speakingKey === key}
                    onCopy={handleCopy}
                    onSpeak={handleSpeak}
                    onOpenSource={handleOpenSource}
                  />
                );
              })}
            </div>
          )}
          <div ref={endRef} className="h-4" />
        </div>
      </div>

      {error && (
        <div className="mx-auto w-full max-w-4xl px-3 md:px-4">
          <div className="mb-2 p-2 md:p-3 rounded-lg text-[10px] md:text-xs text-center font-medium bg-red-500/10 text-red-500 border border-red-500/20">
            {error}
          </div>
        </div>
      )}

      <Composer
        value={input}
        onChange={setInput}
        onSubmit={handleSubmit}
        disabled={isStreaming || historyLoading}
        collections={collections}
        scopeCollectionId={scopeCollectionId}
        onScopeChange={onScopeChange}
      />

      <AnimatePresence>
        {panel && (
          <motion.div
            key="source-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setCitation(null)}
            className="fixed inset-0 z-[60] bg-black/40 backdrop-blur-sm md:hidden"
          />
        )}
      </AnimatePresence>
      <AnimatePresence>
        {panel && (
          <SourcePanel
            key="source-panel"
            sources={panel.sources}
            activeNumber={panel.number}
            onClose={() => setCitation(null)}
            onOpenDocument={(documentId) => {
              setCitation(null);
              onOpenDocument(documentId);
            }}
          />
        )}
      </AnimatePresence>
    </div>
  );
}
