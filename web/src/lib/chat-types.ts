export type Source = {
  id: string;
  content: string;
  metadata: Record<string, unknown>;
  document_id?: string | null;
  document_title?: string | null;
};

export type ChatMessage = {
  id?: string;
  role: 'user' | 'assistant';
  content: string;
  sources?: Source[];
  isStreaming?: boolean;
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
};

export type ConversationDetail = Conversation & { messages: MessageDTO[] };
