import type { Metadata } from 'next';
import { notFound } from 'next/navigation';
import { SharedTranscript } from '@/components/shared/shared-transcript';
import type { SharedChat } from '@/lib/chat-types';
import { getApiKey, getBackendUrl } from '@/lib/server-env';

export const metadata: Metadata = {
  title: 'Shared chat | RAG Evals',
  robots: { index: false, follow: false },
};

export const dynamic = 'force-dynamic';

async function loadSharedChat(token: string): Promise<SharedChat | null> {
  const apiKey = getApiKey();
  if (!apiKey) throw new Error('RAG_API_KEY is not set');

  const res = await fetch(`${getBackendUrl()}/shared/${encodeURIComponent(token)}`, {
    headers: { 'X-API-Key': apiKey },
    cache: 'no-store',
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Shared chat request failed (${res.status})`);
  return (await res.json()) as SharedChat;
}

export default async function SharedChatPage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  const chat = await loadSharedChat(token);
  if (!chat) notFound();
  return <SharedTranscript chat={chat} />;
}
