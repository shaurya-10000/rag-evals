import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

    const response = await fetch(backendUrl + '/ingest', {
      method: 'POST',
      body: formData,
    });
    
    // Safely parse the response (FastAPI might return plain text on 500 errors)
    const text = await response.text();
    let data;
    try {
      data = JSON.parse(text);
    } catch {
      data = { error: text.substring(0, 100) }; // Truncate HTML error pages
    }
    
    if (!response.ok) {
      const errorMsg = data.detail || data.error || 'Backend failed to ingest';
      return NextResponse.json({ error: errorMsg }, { status: response.status });
    }

    return NextResponse.json(data);
  } catch (error) {
    console.error('Ingest error:', error);
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}
