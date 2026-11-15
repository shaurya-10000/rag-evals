import { getApiKey, getBackendUrl } from '../../../lib/server-env';
import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const backendUrl = getBackendUrl();
    const apiKey = getApiKey();
    if (!apiKey) {
      return NextResponse.json({ error: 'Server misconfigured: RAG_API_KEY is not set' }, { status: 500 });
    }
    const cookieStore = await cookies();
    const accessToken = cookieStore.get('access_token')?.value || '';

    const response = await fetch(backendUrl + '/query', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
        'Cookie': `access_token=${accessToken}`
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      console.error("Backend Error:", response.status, await response.text());
      return new NextResponse('Backend rejected request', { status: response.status });
    }

    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch {
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}

