import { backendFetch } from '@/lib/backend-proxy';

export async function GET(req: Request) {
  return backendFetch(req, '/search/conversations', 'GET');
}
