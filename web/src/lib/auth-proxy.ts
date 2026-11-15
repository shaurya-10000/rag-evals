import { NextResponse } from 'next/server';
import { getBackendUrl } from './server-env';

/** Forward a JSON POST to the FastAPI auth backend, passing through any Set-Cookie. */
export async function proxyAuth(req: Request, backendPath: string): Promise<NextResponse> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return NextResponse.json({ detail: 'Invalid request' }, { status: 400 });
  }

  try {
    const response = await fetch(getBackendUrl() + backendPath, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    if (response.status === 429) {
      return NextResponse.json(
        { detail: 'Too many requests. Please wait a minute and try again.' },
        { status: 429 },
      );
    }

    const data = await response.json().catch(() => ({}));
    const headers = new Headers();
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) headers.set('set-cookie', setCookie);
    return NextResponse.json(data, { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: 'Failed to connect to backend' }, { status: 500 });
  }
}
