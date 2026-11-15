import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';
import { getApiKey } from '../../../lib/server-env';

export async function POST(req: Request) {
  const apiKey = getApiKey();
  if (!apiKey) {
    return NextResponse.json({ error: 'Server misconfigured: RAG_API_KEY is not set' }, { status: 500 });
  }

  const headers: Record<string, string> = { 'X-API-Key': apiKey };
  let body: BodyInit;
  try {
    // Paste-text sends JSON, file upload sends multipart. The backend accepts both.
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
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
    const cookieStore = await cookies();
    headers['Cookie'] = `access_token=${cookieStore.get('access_token')?.value || ''}`;

    const response = await fetch(backendUrl + '/ingest', { method: 'POST', headers, body });

    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { error: text.substring(0, 100) }; }

    if (!response.ok) {
      return NextResponse.json(
        { error: data.detail || data.error || 'Backend failed to ingest' },
        { status: response.status }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error('seed proxy error:', error);
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 502 });
  }
}