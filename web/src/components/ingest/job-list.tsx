'use client';

import { AlertCircle, CheckCircle2, ExternalLink, Loader2, X } from 'lucide-react';
import { isActive, type IngestJob } from '@/lib/ingest-types';

type Props = {
  jobs: IngestJob[];
  onDismiss: (id: string) => void;
  onOpenDocument: (documentId: string) => void;
};

const ghostBtn =
  'flex items-center gap-1.5 px-2.5 py-1.5 text-[10px] md:text-xs font-medium text-neutral-600 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200 bg-neutral-100 hover:bg-neutral-200 dark:bg-neutral-800 dark:hover:bg-neutral-700 rounded-md transition-colors';

function percent(job: IngestJob): number | null {
  if (job.status === 'succeeded') return 100;
  const measurable = job.stage === 'embedding' || job.stage === 'saving';
  if (!measurable || job.progress_total <= 0) return null;
  return Math.min(100, Math.round((job.progress_done / job.progress_total) * 100));
}

function describe(job: IngestJob): string {
  if (job.status === 'failed') return job.error ?? 'The import failed.';
  if (job.status === 'succeeded') return job.duplicate ? 'Already in your library.' : 'Added to your library.';
  if (job.status === 'queued') return 'Waiting to start...';
  if (job.stage === 'extracting') {
    return job.kind === 'url' ? 'Fetching and reading the page...' : 'Reading the document...';
  }
  if (job.progress_total > 0) {
    return `Indexing ${job.progress_done} of ${job.progress_total} passages...`;
  }
  return 'Preparing...';
}

function StatusIcon({ job }: { job: IngestJob }) {
  if (job.status === 'failed') return <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-red-500" />;
  if (job.status === 'succeeded') return <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5 text-accent-500" />;
  return <Loader2 className="w-4 h-4 shrink-0 mt-0.5 animate-spin text-accent-500" />;
}

function ProgressBar({ value }: { value: number | null }) {
  return (
    <div
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={value ?? undefined}
      className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800"
    >
      <div
        className={`h-full rounded-full bg-accent-500 transition-all duration-500 ${value === null ? 'w-1/3 animate-pulse' : ''}`}
        style={value === null ? undefined : { width: `${value}%` }}
      />
    </div>
  );
}

export function JobList({ jobs, onDismiss, onOpenDocument }: Props) {
  if (jobs.length === 0) return null;

  return (
    <section aria-label="Recent imports" className="space-y-2">
      <h3 className="text-[10px] md:text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-wider">
        Recent imports
      </h3>
      <ul className="space-y-2">
        {jobs.map((job) => (
          <li
            key={job.id}
            className="rounded-xl border border-neutral-200 dark:border-neutral-800 bg-white dark:bg-neutral-900/50 p-3"
          >
            <div className="flex items-start gap-2.5">
              <StatusIcon job={job} />
              <div className="min-w-0 flex-1">
                <p className="truncate text-xs md:text-sm font-semibold text-neutral-900 dark:text-neutral-100">
                  {job.title}
                </p>
                <p
                  className={`text-[10px] md:text-xs mt-0.5 ${job.status === 'failed' ? 'text-red-500' : 'text-neutral-500'}`}
                >
                  {describe(job)}
                </p>
                {isActive(job) && <ProgressBar value={percent(job)} />}
              </div>
              {job.status === 'succeeded' && job.document_id && (
                <button onClick={() => onOpenDocument(job.document_id as string)} className={ghostBtn}>
                  <ExternalLink className="w-3.5 h-3.5" /> Open
                </button>
              )}
              {!isActive(job) && (
                <button
                  onClick={() => onDismiss(job.id)}
                  className="p-1 rounded-md text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                  aria-label="Dismiss"
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
