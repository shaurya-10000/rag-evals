'use client';

import { useCallback, useRef, useState } from 'react';
import type { ChatMessage, Conversation, MessageDTO } from '@/lib/chat-types';
import { getConversation } from '@/lib/conversations-api';
import { readSse } from '@/lib/sse';

const TITLE_MAX_CHARS = 30;
const TOP_K = 3;

type Options = {
  scopeCollectionId: string;
  createConversation: (title: string) => Promise<Conversation>;
  onFirstMessage: (conversationId: string, prompt: string) => void;
};

const toChatMessage = (m: MessageDTO): ChatMessage => ({
  id: m.id,
  role: m.role,
  content: m.content,
  sources: m.sources,
});

const draftTitle = (query: string) =>
  query.length > TITLE_MAX_CHARS ? `${query.slice(0, TITLE_MAX_CHARS)}...` : query;

function describeQueryFailure(status: number): string {
  if (status === 429) return 'You are asking too quickly. Please wait a minute and try again.';
  if (status === 401 || status === 403) return 'Your session has expired. Please sign in again.';
  if (status === 404) return 'This conversation no longer exists. Start a new chat.';
  if (status === 502 || status === 503) return 'The AI service is busy right now. Please try again in a minute.';
  return 'Something went wrong while answering. Please try again.';
}

/**
 * Chat state keyed by conversation id, so a stream keeps updating its own
 * conversation even if the user switches to another chat while it runs.
 */
export function useChat({ scopeCollectionId, createConversation, onFirstMessage }: Options) {
  const [activeId, setActiveId] = useState<string | null>(null);
  const [messagesById, setMessagesById] = useState<Record<string, ChatMessage[]>>({});
  const [streamingById, setStreamingById] = useState<Record<string, boolean>>({});
  const [historyLoading, setHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeIdRef = useRef<string | null>(null);
  const streamingRef = useRef(new Set<string>());
  const loadedRef = useRef(new Set<string>());

  const activate = useCallback((id: string | null) => {
    activeIdRef.current = id;
    setActiveId(id);
    setError(null);
  }, []);

  const patchMessages = useCallback((id: string, update: (messages: ChatMessage[]) => ChatMessage[]) => {
    setMessagesById((prev) => ({ ...prev, [id]: update(prev[id] ?? []) }));
  }, []);

  const patchLast = useCallback(
    (id: string, update: (message: ChatMessage) => ChatMessage) => {
      patchMessages(id, (messages) => {
        if (messages.length === 0) return messages;
        const next = [...messages];
        next[next.length - 1] = update(next[next.length - 1]);
        return next;
      });
    },
    [patchMessages]
  );

  const setStreaming = useCallback((id: string, value: boolean) => {
    if (value) streamingRef.current.add(id);
    else streamingRef.current.delete(id);
    setStreamingById((prev) => ({ ...prev, [id]: value }));
  }, []);

  const startNewChat = useCallback(() => activate(null), [activate]);

  const selectConversation = useCallback(
    async (id: string) => {
      activate(id);
      if (streamingRef.current.has(id)) return; // the live stream owns this conversation
      if (!loadedRef.current.has(id)) setHistoryLoading(true);
      try {
        const detail = await getConversation(id);
        loadedRef.current.add(id);
        if (!streamingRef.current.has(id)) {
          setMessagesById((prev) => ({ ...prev, [id]: detail.messages.map(toChatMessage) }));
        }
      } catch {
        if (activeIdRef.current === id && !loadedRef.current.has(id)) {
          setError('Could not load this conversation. Please try again.');
        }
      } finally {
        if (activeIdRef.current === id) setHistoryLoading(false);
      }
    },
    [activate]
  );

  const discardConversation = useCallback(
    (id: string) => {
      loadedRef.current.delete(id);
      setMessagesById((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      if (activeIdRef.current === id) activate(null);
    },
    [activate]
  );

  const send = useCallback(
    async (text: string) => {
      const query = text.trim();
      if (!query) return;

      let id = activeIdRef.current;
      if (id && streamingRef.current.has(id)) return;

      const isFirstMessage = id === null;
      setError(null);

      if (id === null) {
        try {
          id = (await createConversation(draftTitle(query))).id;
        } catch {
          setError('Could not start a new chat. Please try again.');
          return;
        }
        loadedRef.current.add(id);
        activate(id);
      }

      const conversationId = id;
      patchMessages(conversationId, (messages) => [
        ...messages,
        { role: 'user', content: query },
        { role: 'assistant', content: '', isStreaming: true },
      ]);
      setStreaming(conversationId, true);
      if (isFirstMessage) onFirstMessage(conversationId, query);

      try {
        const res = await fetch('/api/query', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            query,
            top_k: TOP_K,
            collection_id: scopeCollectionId || undefined,
            conversation_id: conversationId,
          }),
        });
        if (!res.ok || !res.body) throw new Error(describeQueryFailure(res.status));

        for await (const event of readSse(res.body)) {
          if (event.type === 'sources') {
            patchLast(conversationId, (m) => ({ ...m, sources: event.sources }));
          } else if (event.type === 'token') {
            patchLast(conversationId, (m) => ({ ...m, content: m.content + event.text }));
          } else if (event.type === 'error') {
            patchLast(conversationId, (m) => ({
              ...m,
              content: m.content ? `${m.content}\n\n⚠️ ${event.message}` : `⚠️ ${event.message}`,
            }));
          }
        }
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Error connecting to backend.';
        patchLast(conversationId, (m) => ({
          ...m,
          content: m.content ? `${m.content}\n\n⚠️ ${message}` : `⚠️ ${message}`,
        }));
      } finally {
        patchLast(conversationId, (m) => ({
          ...m,
          isStreaming: false,
          content: m.content || '⚠️ No response was received. Please try again.',
        }));
        setStreaming(conversationId, false);
      }
    },
    [scopeCollectionId, createConversation, onFirstMessage, activate, patchMessages, patchLast, setStreaming]
  );

  const messages = activeId ? (messagesById[activeId] ?? []) : [];
  const isStreaming = activeId ? Boolean(streamingById[activeId]) : false;

  return {
    activeId,
    messages,
    isStreaming,
    historyLoading,
    error,
    send,
    startNewChat,
    selectConversation,
    discardConversation,
  };
}
