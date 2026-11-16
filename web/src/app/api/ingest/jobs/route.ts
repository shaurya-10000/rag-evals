import { backendFetch } from '@/lib/backend-proxy';
import { proxyIngest } from '@/lib/ingest-proxy';

export async function GET(req: Request) {
  return backendFetch(req, '/ingest/jobs', 'GET');
}

export async function POST(req: Request) {
  return proxyIngest(req, '/ingest/jobs');
}
