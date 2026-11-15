import { backendFetch } from '@/lib/backend-proxy';

export async function GET(req: Request) {
  return backendFetch(req, '/conversations', 'GET');
}

export async function POST(req: Request) {
  return backendFetch(req, '/conversations', 'POST');
}
