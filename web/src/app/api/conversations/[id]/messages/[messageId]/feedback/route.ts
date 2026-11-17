import { backendFetch } from '@/lib/backend-proxy';

type Params = { params: Promise<{ id: string; messageId: string }> };

async function target({ params }: Params) {
  const { id, messageId } = await params;
  return `/conversations/${encodeURIComponent(id)}/messages/${encodeURIComponent(messageId)}/feedback`;
}

export async function PUT(req: Request, ctx: Params) {
  return backendFetch(req, await target(ctx), 'PUT');
}

export async function DELETE(req: Request, ctx: Params) {
  return backendFetch(req, await target(ctx), 'DELETE');
}
