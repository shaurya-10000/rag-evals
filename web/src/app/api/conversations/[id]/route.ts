import { backendFetch, type IdParams } from '@/lib/backend-proxy';

export async function GET(req: Request, { params }: IdParams) {
  const { id } = await params;
  return backendFetch(req, `/conversations/${encodeURIComponent(id)}`, 'GET');
}

export async function PATCH(req: Request, { params }: IdParams) {
  const { id } = await params;
  return backendFetch(req, `/conversations/${encodeURIComponent(id)}`, 'PATCH');
}

export async function DELETE(req: Request, { params }: IdParams) {
  const { id } = await params;
  return backendFetch(req, `/conversations/${encodeURIComponent(id)}`, 'DELETE');
}
