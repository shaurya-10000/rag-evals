'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Conversation } from '@/lib/chat-types';
import * as api from '@/lib/conversations-api';
import { clearLegacyChats, readLegacyChats } from '@/lib/legacy-chats';

const IMPORT_ATTEMPTED_KEY = 'rag-evals-chats-import-attempted';
const DEFAULT_TITLE = 'New Chat';

// Shared across effect re-runs (React StrictMode) so the import can never fire twice.
let legacyImport: Promise<void> | null = null;

function importLegacyChatsOnce(): Promise<void> {
  if (legacyImport) return legacyImport;
  legacyImport = (async () => {
    try {
      if (window.sessionStorage.getItem(IMPORT_ATTEMPTED_KEY)) return;
      const legacy = readLegacyChats();
      if (legacy.length === 0) {
        clearLegacyChats();
        return;
      }
      window.sessionStorage.setItem(IMPORT_ATTEMPTED_KEY, '1');
      await api.importConversations(legacy);
      clearLegacyChats();
    } catch {
      /* keep the legacy data; the next session retries */
    }
  })();
  return legacyImport;
}

const messageOf = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback);

export function useConversations() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(conversations);

  useEffect(() => {
    latest.current = conversations;
  });

  const refresh = useCallback(async () => {
    try {
      setConversations(await api.listConversations());
      setError(null);
    } catch (err) {
      setError(messageOf(err, 'Failed to load chats'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    importLegacyChatsOnce()
      .then(() => api.listConversations())
      .then((list) => {
        if (cancelled) return;
        setConversations(list);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(messageOf(err, 'Failed to load chats'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const create = useCallback(async (title: string): Promise<Conversation> => {
    const created = await api.createConversation(title);
    setConversations((prev) => [created, ...prev.filter((c) => c.id !== created.id)]);
    return created;
  }, []);

  /** Optimistic update; rolls back if the server rejects it. */
  const patch = useCallback(async (id: string, change: { title?: string; pinned?: boolean }) => {
    const previous = latest.current.find((c) => c.id === id);
    if (!previous) return;
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...change } : c)));
    try {
      const updated = await api.updateConversation(id, change);
      setConversations((prev) => prev.map((c) => (c.id === id ? updated : c)));
    } catch {
      setConversations((prev) => prev.map((c) => (c.id === id ? previous : c)));
    }
  }, []);

  const rename = useCallback(
    async (id: string, title: string) => {
      const trimmed = title.trim();
      if (trimmed) await patch(id, { title: trimmed });
    },
    [patch]
  );

  const togglePin = useCallback(
    async (id: string) => {
      const current = latest.current.find((c) => c.id === id);
      if (current) await patch(id, { pinned: !current.pinned });
    },
    [patch]
  );

  const remove = useCallback(
    async (id: string): Promise<boolean> => {
      try {
        await api.deleteConversation(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        return true;
      } catch (err) {
        setError(messageOf(err, 'Failed to delete chat'));
        await refresh();
        return false;
      }
    },
    [refresh]
  );

  const generateTitle = useCallback(
    async (id: string, prompt: string) => {
      try {
        const res = await fetch('/api/generate-title', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ prompt }),
        });
        const data: { title?: string } = await res.json();
        if (data.title && data.title !== DEFAULT_TITLE) await patch(id, { title: data.title });
      } catch {
        /* keep the placeholder title */
      }
    },
    [patch]
  );

  return { conversations, loading, error, create, rename, togglePin, remove, generateTitle };
}
