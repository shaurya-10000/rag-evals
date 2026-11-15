'use client';

import { memo, useMemo } from 'react';
import ReactMarkdown, { type Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { linkCitations, parseCitationHref } from '@/lib/citations';

type Props = {
  content: string;
  sourceCount: number;
  onCite: (sourceNumber: number) => void;
};

/** react-markdown passes its AST node as a prop; keep it off the DOM. */
function omitNode<T extends { node?: unknown }>(props: T): Omit<T, 'node'> {
  const { node, ...rest } = props;
  void node;
  return rest;
}

export const AssistantMarkdown = memo(function AssistantMarkdown({ content, sourceCount, onCite }: Props) {
  const text = useMemo(() => linkCitations(content, sourceCount), [content, sourceCount]);

  const components = useMemo<Components>(
    () => ({
      table: (props) => (
        <div className="overflow-x-auto my-4 md:my-6 rounded-lg border border-neutral-200 dark:border-neutral-800">
          <table className="min-w-full divide-y divide-neutral-200 dark:divide-neutral-800" {...omitNode(props)} />
        </div>
      ),
      thead: (props) => <thead className="bg-neutral-100 dark:bg-neutral-900/50" {...omitNode(props)} />,
      th: (props) => (
        <th
          className="px-2 md:px-4 py-2 md:py-3 text-left text-[10px] md:text-xs font-semibold text-neutral-900 dark:text-neutral-100 uppercase tracking-wider"
          {...omitNode(props)}
        />
      ),
      td: (props) => (
        <td
          className="px-2 md:px-4 py-2 md:py-3 text-xs md:text-sm text-neutral-700 dark:text-neutral-300 border-t border-neutral-200 dark:border-neutral-800"
          {...omitNode(props)}
        />
      ),
      a: ({ href, children }) => {
        const sourceNumber = parseCitationHref(href);
        if (sourceNumber !== null) {
          return (
            <button
              type="button"
              onClick={() => onCite(sourceNumber)}
              aria-label={`Open source ${sourceNumber}`}
              className="inline-flex items-center justify-center min-w-[1.25rem] h-5 px-1 mx-0.5 align-baseline rounded-md bg-accent-500/15 text-accent-600 dark:text-accent-400 text-[11px] font-semibold hover:bg-accent-500/30 transition-colors cursor-pointer"
            >
              {sourceNumber}
            </button>
          );
        }
        return (
          <a
            href={href}
            className="text-accent-600 hover:underline font-medium"
            target="_blank"
            rel="noopener noreferrer"
          >
            {children}
          </a>
        );
      },
    }),
    [onCite]
  );

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {text}
    </ReactMarkdown>
  );
});
