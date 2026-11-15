export type PassageRange = { start: number; end: number };

const HEAD_TAIL_WORDS = 12;
const MIN_WORDS_FOR_FALLBACK = HEAD_TAIL_WORDS * 2;
const MAX_SPAN_FACTOR = 2;

const escapeRegExp = (value: string) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
const toWords = (text: string) => text.split(/\s+/).filter(Boolean);

/** Cleans stray indentation and blank-line runs so a passage reads well in the UI. */
export function tidyPassage(text: string): string {
  return text
    .replace(/\r\n/g, '\n')
    .split('\n')
    .map((line) => line.replace(/\s+$/, '').replace(/(\S)[ \t]{2,}(?=\S)/g, '$1 '))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function findWords(content: string, words: string[], from = 0): PassageRange | null {
  if (words.length === 0) return null;
  const pattern = new RegExp(words.map(escapeRegExp).join('\\s+'), 'g');
  pattern.lastIndex = from;
  const match = pattern.exec(content);
  return match ? { start: match.index, end: match.index + match[0].length } : null;
}

/**
 * Finds where a cited passage sits inside the document text, ignoring whitespace
 * differences. If the middle of the passage changed, falls back to matching its
 * opening and closing words. Returns null when the passage cannot be found.
 */
export function locatePassage(content: string, passage: string): PassageRange | null {
  const words = toWords(passage);
  if (words.length === 0) return null;

  const exact = findWords(content, words);
  if (exact) return exact;
  if (words.length < MIN_WORDS_FOR_FALLBACK) return null;

  const head = findWords(content, words.slice(0, HEAD_TAIL_WORDS));
  if (!head) return null;
  const tail = findWords(content, words.slice(-HEAD_TAIL_WORDS), head.end);
  if (!tail) return null;
  if (tail.end - head.start > passage.length * MAX_SPAN_FACTOR) return null;
  return { start: head.start, end: tail.end };
}
