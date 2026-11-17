export type Source = {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  document_id?: string | null;
  document_title?: string | null;
  document_available?: boolean | null;
};

export type ChatMessage = {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
  /** Standalone query the follow-up was rewritten into. */
  rewrittenQuery?: string | null;
  /** True when nothing relevant was found and the answer was withheld. */
  refused?: boolean;
  /** Id of the saved message, once it exists. Needed to rate an answer. */
  messageId?: string;
  feedback?: 1 | -1 | null;
  feedbackComment?: string | null;
};

export type Conversation = {
  id: string;
  title: string;
  pinned: boolean;
  created_at: string;
  updated_at: string;
};

export type MessageDTO = {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  sources: Source[];
  created_at: string;
  rewritten_query?: string | null;
  refused?: boolean;
  feedback?: 1 | -1 | null;
  feedback_comment?: string | null;
};

export type ConversationDetail = Conversation & { messages: MessageDTO[] };

export type SearchHit = {
  id: string;
  title: string;
  pinned: boolean;
  updated_at: string;
  snippet: string | null;
};

export type ShareInfo = {
  shared: boolean;
  token: string | null;
  created_at: string | null;
  updated_at: string | null;
};

export type SharedSource = { document_title: string | null; content: string };
export type SharedMessage = { role: 'user' | 'assistant'; content: string; sources: SharedSource[] };
export type SharedChat = { title: string; shared_at: string; messages: SharedMessage[] };
