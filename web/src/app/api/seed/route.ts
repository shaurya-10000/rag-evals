import { proxyIngest } from '@/lib/ingest-proxy';

export async function POST(req: Request) {
  return proxyIngest(req, '/ingest');
}
