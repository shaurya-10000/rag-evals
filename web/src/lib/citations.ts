export const CITATION_HREF_PREFIX = '#cite-';

// Matches [1], [2, 3] but not markdown links such as [1](https://...).
const CITATION_PATTERN = /\[(\d+(?:\s*,\s*\d+)*)\](?!\()/g;

/** Rewrites "[1]" / "[1, 2]" in model output into internal links the renderer turns into chips. */
export function linkCitations(markdown: string, sourceCount: number): string {
  if (sourceCount === 0) return markdown;
  return markdown.replace(CITATION_PATTERN, (match: string, group: string) => {
    const numbers = group.split(',').map((n) => Number.parseInt(n.trim(), 10));
    if (numbers.some((n) => n < 1 || n > sourceCount)) return match;
    return numbers.map((n) => `[${n}](${CITATION_HREF_PREFIX}${n})`).join('');
  });
}

export function parseCitationHref(href: string | undefined): number | null {
  if (!href?.startsWith(CITATION_HREF_PREFIX)) return null;
  const value = Number.parseInt(href.slice(CITATION_HREF_PREFIX.length), 10);
  return Number.isNaN(value) ? null : value;
}
