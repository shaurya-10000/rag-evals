import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  try {
    const response = await fetch(backendUrl + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    const data = await response.json();
    const setCookie = response.headers.get('set-cookie');
    const headers = new Headers();
    if (setCookie) headers.set('set-cookie', setCookie);
    return NextResponse.json(data, { status: response.status, headers });
  } catch {
    return NextResponse.json({ detail: 'Failed to connect to backend' }, { status: 500 });
  }
}
