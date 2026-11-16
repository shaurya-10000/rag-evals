import type { IngestJob } from './ingest-types';

export type JobInput =
  | { kind: 'text'; title: string; text: string; collectionId: string }
  | { kind: 'file'; title: string; file: File; collectionId: string }
  | { kind: 'url'; title: string; url: string; collectionId: string };

async function readJson<T>(res: Response, fallback: string): Promise<T> {
  let data: unknown = null;
  try {
    data = await res.json();
  } catch {
    /* empty body */
  }
  if (!res.ok) {
    throw new Error((data as { error?: string } | null)?.error || fallback);
  }
  return data as T;
}

export async function createIngestJob(input: JobInput): Promise<IngestJob> {
  const collectionId = input.collectionId || undefined;
  let init: RequestInit;

  if (input.kind === 'file') {
    const form = new FormData();
    form.append('file', input.file);
    form.append('title', input.title);
    if (collectionId) form.append('collection_id', collectionId);
    init = { method: 'POST', body: form };
  } else {
    const body =
      input.kind === 'url'
        ? { url: input.url, title: input.title || undefined, collection_id: collectionId }
        : { text: input.text, title: input.title, collection_id: collectionId };
    init = {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    };
  }
  return readJson<IngestJob>(await fetch('/api/ingest/jobs', init), 'Could not start the import');
}

export async function listIngestJobs(): Promise<IngestJob[]> {
  return readJson<IngestJob[]>(
    await fetch('/api/ingest/jobs', { cache: 'no-store' }),
    'Could not load imports'
  );
}
