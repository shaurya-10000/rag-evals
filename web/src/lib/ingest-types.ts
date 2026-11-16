export type JobStatus = 'queued' | 'running' | 'succeeded' | 'failed';
export type JobStage = 'queued' | 'extracting' | 'embedding' | 'saving' | 'done';

export type IngestJob = {
  id: string;
  kind: 'text' | 'file' | 'url';
  title: string;
  status: JobStatus;
  stage: JobStage;
  progress_done: number;
  progress_total: number;
  document_id: string | null;
  duplicate: boolean;
  error: string | null;
  created_at: string;
  finished_at: string | null;
};

export const isActive = (job: IngestJob) => job.status === 'queued' || job.status === 'running';
