'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { listIngestJobs } from '@/lib/ingest-api';
import { isActive, type IngestJob, type JobStatus } from '@/lib/ingest-types';

const POLL_MS = 2000;

/**
 * Recent imports. Polls while any of them is running, and calls `onSucceeded` once
 * per job that finishes during this session (not for jobs that were already done).
 */
export function useIngestJobs(onSucceeded: () => void | Promise<void>) {
  const [jobs, setJobs] = useState<IngestJob[]>([]);
  const [dismissed, setDismissed] = useState<ReadonlySet<string>>(new Set());
  const seenStatus = useRef(new Map<string, JobStatus>());
  const onSucceededRef = useRef(onSucceeded);

  useEffect(() => {
    onSucceededRef.current = onSucceeded;
  }, [onSucceeded]);

  const apply = useCallback((incoming: IngestJob[]) => {
    for (const job of incoming) {
      const previous = seenStatus.current.get(job.id);
      if (previous && previous !== 'succeeded' && job.status === 'succeeded' && !job.duplicate) {
        void onSucceededRef.current();
      }
      seenStatus.current.set(job.id, job.status);
    }
    setJobs(incoming);
  }, []);

  const track = useCallback((job: IngestJob) => {
    seenStatus.current.set(job.id, job.status);
    setJobs((current) => [job, ...current.filter((existing) => existing.id !== job.id)]);
  }, []);

  const dismiss = useCallback((id: string) => {
    setDismissed((current) => new Set(current).add(id));
  }, []);

  useEffect(() => {
    let cancelled = false;
    listIngestJobs()
      .then((list) => {
        if (!cancelled) apply(list);
      })
      .catch(() => {
        /* the list stays empty until the next import */
      });
    return () => {
      cancelled = true;
    };
  }, [apply]);

  const hasActive = jobs.some(isActive);
  useEffect(() => {
    if (!hasActive) return;
    let cancelled = false;
    const timer = window.setInterval(() => {
      listIngestJobs()
        .then((list) => {
          if (!cancelled) apply(list);
        })
        .catch(() => {
          /* keep polling */
        });
    }, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [hasActive, apply]);

  const visible = useMemo(() => jobs.filter((job) => !dismissed.has(job.id)), [jobs, dismissed]);
  return { jobs: visible, track, dismiss };
}
