import type { Source } from './chat-types';

/** One-time migration of the old LocalStorage chat history into Postgres. */
const LEGACY_KEY = 'rag-evals-chats';
const MAX_CONVERSATIONS = 100;
const MAX_MESSAGES = 500;
const MAX_CONTENT_CHARS = 100_000;
const MAX_SOURCES = 20;

export type ImportMessage = { role: 'user' | 'assistant'; content: string; sources: Source[] };
export type ImportConversation = {
  title: string;
  pinned: boolean;
  created_at: string;
  messages: ImportMessage[];
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

function toImportMessages(raw: unknown): ImportMessage[] {
  if (!Array.isArray(raw)) return [];
  const messages: ImportMessage[] = [];
  for (const item of raw) {
    if (!isRecord(item)) continue;
    const { role, content } = item;
    if ((role !== 'user' && role !== 'assistant') || typeof content !== 'string' || !content.trim()) {
      continue;
    }
    const sources = Array.isArray(item.chunks)
      ? (item.chunks.filter(isRecord) as unknown as Source[]).slice(0, MAX_SOURCES)
      : [];
    messages.push({ role, content: content.slice(0, MAX_CONTENT_CHARS), sources });
  }
  return messages.slice(-MAX_MESSAGES);
}

export function readLegacyChats(): ImportConversation[] {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(LEGACY_KEY);
  } catch {
    return [];
  }
  if (!raw) return [];

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return [];
  }
  if (!Array.isArray(parsed)) return [];

  const result: ImportConversation[] = [];
  for (const chat of parsed) {
    if (!isRecord(chat)) continue;
    const messages = toImportMessages(chat.messages);
    if (messages.length === 0) continue;
    const createdAt = typeof chat.createdAt === 'number' ? chat.createdAt : Date.now();
    result.push({
      title: (typeof chat.title === 'string' && chat.title.trim() ? chat.title : 'New Chat').slice(0, 255),
      pinned: chat.pinned === true,
      created_at: new Date(createdAt).toISOString(),
      messages,
    });
  }
  return result.slice(0, MAX_CONVERSATIONS);
}

export function clearLegacyChats(): void {
  try {
    window.localStorage.removeItem(LEGACY_KEY);
  } catch {
    /* storage unavailable */
  }
}
