import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { getApiKey, getBackendUrl } from './server-env';

type Method = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';

/** Forward a request to FastAPI with the API key + the user's auth cookie. */
export async function backendFetch(req: Request, path: string, method: Method): Promise<NextResponse> {
  const apiKey = getApiKey();
  if (!apiKey) {
    return NextResponse.json({ error: 'Server misconfigured: RAG_API_KEY is not set' }, { status: 500 });
  }

  const cookieStore = await cookies();
  const headers: Record<string, string> = {
    'X-API-Key': apiKey,
    Cookie: `access_token=${cookieStore.get('access_token')?.value || ''}`,
  };

  let body: string | undefined;
  if (method !== 'GET' && method !== 'DELETE') {
    try {
      body = JSON.stringify(await req.json());
      headers['Content-Type'] = 'application/json';
    } catch {
      return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
    }
  }

  const search = new URL(req.url).search;
  try {
    const response = await fetch(getBackendUrl() + path + search, {
      method,
      headers,
      body,
      cache: 'no-store',
    });

    const text = await response.text();
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.substring(0, 100) };
    }

    if (!response.ok) {
      const detail = data.detail;
      const message =
        typeof detail === 'string' ? detail : typeof data.error === 'string' ? data.error : 'Request failed';
      return NextResponse.json({ error: message }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('backend proxy error:', error);
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 502 });
  }
}

export type IdParams = { params: Promise<{ id: string }> };