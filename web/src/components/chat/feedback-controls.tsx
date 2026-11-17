'use client';

import { ThumbsDown, ThumbsUp } from 'lucide-react';

const REASONS = ['Wrong answer', 'Not in my documents', 'Too vague', 'Hard to read'];

type ButtonsProps = {
  rating: 1 | -1 | null | undefined;
  onRate: (rating: 1 | -1) => void;
  buttonClass: string;
};

export function FeedbackButtons({ rating, onRate, buttonClass }: ButtonsProps) {
  return (
    <>
      <button
        type="button"
        onClick={() => onRate(1)}
        className={buttonClass}
        title="Good answer"
        aria-label="Good answer"
        aria-pressed={rating === 1}
      >
        <ThumbsUp className={`w-3.5 h-3.5 ${rating === 1 ? 'fill-current text-accent-500' : ''}`} />
      </button>
      <button
        type="button"
        onClick={() => onRate(-1)}
        className={buttonClass}
        title="Bad answer"
        aria-label="Bad answer"
        aria-pressed={rating === -1}
      >
        <ThumbsDown className={`w-3.5 h-3.5 ${rating === -1 ? 'fill-current text-red-500' : ''}`} />
      </button>
    </>
  );
}

export function FeedbackReasons({ onPick }: { onPick: (reason: string) => void }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5">
      <span className="text-[10px] md:text-xs text-neutral-500">What went wrong?</span>
      {REASONS.map((reason) => (
        <button
          key={reason}
          type="button"
          onClick={() => onPick(reason)}
          className="px-2 py-1 rounded-full border border-neutral-200 dark:border-neutral-800 text-[10px] md:text-xs text-neutral-600 dark:text-neutral-300 hover:bg-neutral-100 dark:hover:bg-neutral-800 transition-colors"
        >
          {reason}
        </button>
      ))}
    </div>
  );
}
