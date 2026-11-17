import type { ConversationDetail } from './chat-types';
import { getConversation } from './conversations-api';

const EXCERPT_CHARS = 160;

const excerpt = (text: string) => {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > EXCERPT_CHARS ? `${flat.slice(0, EXCERPT_CHARS)}...` : flat;
};

const fileName = (title: string) =>
  `${title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'chat'}.md`;

export function chatToMarkdown(chat: ConversationDetail): string {
  const lines = [`# ${chat.title}`, '', `Exported ${new Date().toLocaleString()} from RAG Evals.`, ''];
  for (const message of chat.messages) {
    lines.push(message.role === 'user' ? '## You' : '## Assistant', '', message.content.trim(), '');
    if (message.role === 'assistant' && message.sources.length > 0) {
      lines.push('**Sources**', '');
      message.sources.forEach((source, index) => {
        lines.push(`${index + 1}. ${source.document_title ?? 'Unknown document'}: "${excerpt(source.content)}"`);
      });
      lines.push('');
    }
  }
  return lines.join('\n');
}

function download(filename: string, text: string, type: string) {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function exportConversationMarkdown(id: string): Promise<void> {
  const chat = await getConversation(id);
  download(fileName(chat.title), chatToMarkdown(chat), 'text/markdown;charset=utf-8');
}
