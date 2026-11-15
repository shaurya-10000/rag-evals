import type { Conversation, ConversationDetail } from './chat-types';
import type { ImportConversation } from './legacy-chats';

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: 'no-store', ...init });
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    const message = (data as { error?: string } | null)?.error;
    throw new Error(message || `Request failed (${res.status})`);
  }
  return data as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

const path = (id: string) => `/api/conversations/${encodeURIComponent(id)}`;

export const listConversations = () => request<Conversation[]>('/api/conversations');

export const createConversation = (title?: string) =>
  request<Conversation>('/api/conversations', json('POST', { title }));

export const getConversation = (id: string) => request<ConversationDetail>(path(id));

export const updateConversation = (id: string, change: { title?: string; pinned?: boolean }) =>
  request<Conversation>(path(id), json('PATCH', change));

export const deleteConversation = (id: string) =>
  request<{ status: string }>(path(id), { method: 'DELETE' });

export const importConversations = (conversations: ImportConversation[]) =>
  request<{ imported: number }>('/api/conversations/import', json('POST', { conversations }));
