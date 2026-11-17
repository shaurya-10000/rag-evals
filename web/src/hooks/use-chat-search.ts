'use client';

import { useEffect, useState } from 'react';
import type { SearchHit } from '@/lib/chat-types';
import { searchConversations } from '@/lib/conversations-api';

const DEBOUNCE_MS = 300;

type Result = { query: string; hits: SearchHit[]; error: string | null };

/** Debounced search across chat titles and message text. */
export function useChatSearch(query: string) {
  const [result, setResult] = useState<Result>({ query: '', hits: [], error: null });
  const trimmed = query.trim();

  useEffect(() => {
    if (!trimmed) return;
    let cancelled = false;
    const timer = window.setTimeout(() => {
      searchConversations(trimmed)
        .then((hits) => {
          if (!cancelled) setResult({ query: trimmed, hits, error: null });
        })
        .catch(() => {
          if (!cancelled) setResult({ query: trimmed, hits: [], error: 'Search failed. Try again.' });
        });
    }, DEBOUNCE_MS);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [trimmed]);

  const ready = result.query === trimmed;
  return {
    active: trimmed !== '',
    loading: trimmed !== '' && !ready,
    hits: ready ? result.hits : [],
    error: ready ? result.error : null,
  };
}
