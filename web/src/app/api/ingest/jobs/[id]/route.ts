import { backendFetch, type IdParams } from '@/lib/backend-proxy';

export async function GET(req: Request, { params }: IdParams) {
  const { id } = await params;
  return backendFetch(req, `/ingest/jobs/${encodeURIComponent(id)}`, 'GET');
}
