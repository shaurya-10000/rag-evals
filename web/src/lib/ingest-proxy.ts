import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { getApiKey, getBackendUrl } from './server-env';
import { forwardHeaders } from './forward-headers';
import { WEB_UPLOAD_LIMIT_MB } from './limits';

const MAX_BODY_BYTES = (WEB_UPLOAD_LIMIT_MB + 0.2) * 1024 * 1024;

/** Forward an ingest request (JSON or multipart) to FastAPI with the API key and auth cookie. */
export async function proxyIngest(req: Request, backendPath: string): Promise<NextResponse> {
  const apiKey = getApiKey();
  if (!apiKey) {
    return NextResponse.json({ error: 'Server misconfigured: RAG_API_KEY is not set' }, { status: 500 });
  }

  // Vercel refuses bodies above ~4.5 MB before this code runs; answer clearly if one still arrives.
  const declared = Number(req.headers.get('content-length') ?? 0);
  if (declared > MAX_BODY_BYTES) {
    return NextResponse.json(
      { error: `That file is too large to upload here (max ${WEB_UPLOAD_LIMIT_MB} MB).` },
      { status: 413 }
    );
  }

  const headers: Record<string, string> = { ...forwardHeaders(req), 'X-API-Key': apiKey };
  let body: BodyInit;
  try {
    // Pasted text and URLs are JSON, file uploads are multipart. The backend accepts both.
    if ((req.headers.get('content-type') || '').includes('application/json')) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(await req.json());
    } else {
      body = await req.formData();
    }
  } catch {
    return NextResponse.json({ error: 'Invalid request body' }, { status: 400 });
  }

  try {
    const cookieStore = await cookies();
    headers['Cookie'] = `access_token=${cookieStore.get('access_token')?.value || ''}`;

    const response = await fetch(getBackendUrl() + backendPath, { method: 'POST', headers, body });

    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.substring(0, 100) };
    }

    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || 'Backend failed to ingest' },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('ingest proxy error:', error);
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 502 });
  }
}
