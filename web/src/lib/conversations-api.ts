import type { Conversation, ConversationDetail, SearchHit, ShareInfo } from './chat-types';
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

export const searchConversations = (query: string) =>
  request<SearchHit[]>(`/api/search/conversations?q=${encodeURIComponent(query)}`);

export const getShare = (id: string) => request<ShareInfo>(`${path(id)}/share`);

export const createShare = (id: string) => request<ShareInfo>(`${path(id)}/share`, json('POST', {}));

export const deleteShare = (id: string) => request<ShareInfo>(`${path(id)}/share`, { method: 'DELETE' });

type FeedbackResult = { message_id: string; rating: number | null; comment: string | null };

const feedbackPath = (conversationId: string, messageId: string) =>
  `${path(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`;

export const setMessageFeedback = (
  conversationId: string,
  messageId: string,
  rating: 1 | -1,
  comment: string | null
) => request<FeedbackResult>(feedbackPath(conversationId, messageId), json('PUT', { rating, comment }));

export const clearMessageFeedback = (conversationId: string, messageId: string) =>
  request<FeedbackResult>(feedbackPath(conversationId, messageId), { method: 'DELETE' });
