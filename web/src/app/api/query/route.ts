import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();
  
  // Use the production URL if set, otherwise fallback to localhost for local dev
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
  const targetUrl = backendUrl + '/query';

  try {
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}
