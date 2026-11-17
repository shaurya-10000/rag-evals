import { backendFetch, type IdParams } from '@/lib/backend-proxy';

const target = async ({ params }: IdParams) => `/conversations/${encodeURIComponent((await params).id)}/share`;

export async function GET(req: Request, ctx: IdParams) {
  return backendFetch(req, await target(ctx), 'GET');
}

export async function POST(req: Request, ctx: IdParams) {
  return backendFetch(req, await target(ctx), 'POST');
}

export async function DELETE(req: Request, ctx: IdParams) {
  return backendFetch(req, await target(ctx), 'DELETE');
}
