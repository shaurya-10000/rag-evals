import { backendFetch, type IdParams } from '../../../../../lib/backend-proxy';

export async function PUT(req: Request, { params }: IdParams) {
  const { id } = await params;
  return backendFetch(req, `/documents/${encodeURIComponent(id)}/collection`, 'PUT');
}