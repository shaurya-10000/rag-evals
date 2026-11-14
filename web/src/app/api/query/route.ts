import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  const body = await req.json();
  
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
  const targetUrl = backendUrl + '/query';

  try {
    const response = await fetch(targetUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    // Pass the stream straight through to the client
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
      },
    });
  } catch (error) {
    console.error('Query error:', error);
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}
