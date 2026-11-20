import { proxyAccount } from '@/lib/account-proxy';

export async function DELETE(req: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return proxyAccount(req, `/account/sessions/${encodeURIComponent(id)}`, 'DELETE');
}
