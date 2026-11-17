import type { Source } from './chat-types';

export type StreamEvent =
  | { type: 'sources'; sources: Source[] }
  | { type: 'token'; text: string }
  | { type: 'done'; timings?: string; rewritten_query?: string | null; refused?: boolean; message_id?: string | null }
  | { type: 'error'; message: string };

const KNOWN_TYPES = new Set(['sources', 'token', 'done', 'error']);

function parseFrame(frame: string): StreamEvent | null {
  for (const line of frame.split('\n')) {
    if (!line.startsWith('data:')) continue;
    const payload = line.slice(5).trim();
    if (!payload) continue;
    try {
      const parsed: unknown = JSON.parse(payload);
      const type = (parsed as { type?: unknown } | null)?.type;
      if (typeof type === 'string' && KNOWN_TYPES.has(type)) return parsed as StreamEvent;
    } catch {
      console.error('Malformed SSE frame');
    }
  }
  return null;
}

/** Yields typed events from a Server-Sent Events response body. */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<StreamEvent, void, undefined> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split('\n\n');
      buffer = frames.pop() ?? '';
      for (const frame of frames) {
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
    buffer += decoder.decode();
    const last = parseFrame(buffer);
    if (last) yield last;
  } finally {
    reader.releaseLock();
  }
}