import { NextResponse } from 'next/server';
import { getBackendUrl } from './server-env';
import { forwardHeaders } from './forward-headers';

/** Forward a signed-in account request to FastAPI with the API key and the session cookie. */
export async function proxyAccount(
  req: Request,
  backendPath: string,
  method: 'GET' | 'POST' | 'DELETE',
  withBody = false,
): Promise<NextResponse> {
  const headers: Record<string, string> = {
    'X-API-Key': process.env.RAG_API_KEY ?? '',
    ...forwardHeaders(req),
    Accept: 'application/json',
  };
  const cookie = req.headers.get('cookie');
  if (cookie) headers.Cookie = cookie;

  let body: string | undefined;
  if (withBody) {
    try {
      body = JSON.stringify(await req.json());
    } catch {
      return NextResponse.json({ detail: 'Invalid request' }, { status: 400 });
    }
    headers['Content-Type'] = 'application/json';
  }

  try {
    const response = await fetch(getBackendUrl() + backendPath, {
      method,
      headers,
      body,
      cache: 'no-store',
    });
    if (response.status === 429) {
      return NextResponse.json(
        { detail: 'Too many attempts. Please wait a minute and try again.' },
        { status: 429 },
      );
    }
    const data = await response.json().catch(() => ({}));
    const out = NextResponse.json(data, { status: response.status });
    if (response.status === 401) out.cookies.delete('access_token');
    for (const value of response.headers.getSetCookie()) out.headers.append('set-cookie', value);
    return out;
  } catch {
    return NextResponse.json({ detail: 'Failed to connect to backend' }, { status: 500 });
  }
}
