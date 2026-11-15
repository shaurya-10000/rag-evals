import { backendFetch } from '@/lib/backend-proxy';

export async function POST(req: Request) {
  return backendFetch(req, '/conversations/import', 'POST');
}
