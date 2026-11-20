import type { Metadata } from 'next';
import { Suspense, type ReactNode } from 'react';
import { SharedTranscript } from '@/components/shared/shared-transcript';
import type { SharedChat } from '@/lib/chat-types';
import { getApiKey, getBackendUrl } from '@/lib/server-env';

export const metadata: Metadata = {
  title: 'Shared chat | RAG Evals',
  robots: { index: false, follow: false },
};

type PageProps = { params: Promise<{ token: string }> };

async function loadSharedChat(token: string): Promise<SharedChat | null> {
  const apiKey = getApiKey();
  if (!apiKey) throw new Error('RAG_API_KEY is not set');

  const res = await fetch(`${getBackendUrl()}/shared/${encodeURIComponent(token)}`, {
    headers: { 'X-API-Key': apiKey },
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Shared chat request failed (${res.status})`);
  return (await res.json()) as SharedChat;
}

function Notice({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-[100dvh] flex items-center justify-center p-6 bg-background text-foreground">
      <p className="max-w-sm text-center text-sm text-neutral-500">{children}</p>
    </div>
  );
}

// Request-time data (the token and the backend call) has to sit inside <Suspense>
// when Cache Components is enabled.
async function SharedChatContent({ params }: PageProps) {
  const { token } = await params;
  const chat = await loadSharedChat(token);
  if (!chat) {
    return <Notice>This shared chat is no longer available. The link may have been stopped or never existed.</Notice>;
  }
  return <SharedTranscript chat={chat} />;
}

export default function SharedChatPage({ params }: PageProps) {
  return (
    <Suspense fallback={<Notice>Loading shared chat...</Notice>}>
      <SharedChatContent params={params} />
    </Suspense>
  );
}
