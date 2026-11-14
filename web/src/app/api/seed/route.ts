import { cookies } from 'next/headers';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const formData = await req.formData();
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';
    const cookieStore = await cookies();
    const accessToken = cookieStore.get('access_token')?.value || '';

    const response = await fetch(backendUrl + '/ingest', {
      method: 'POST',
      headers: { 
        'X-API-Key': process.env.RAG_API_KEY || 'dev-secret-key-change-in-production',
        'Cookie': `access_token=${accessToken}`
      },
      body: formData,
    });
    
    const text = await response.text();
    let data;
    try { data = JSON.parse(text); } catch { data = { error: text.substring(0, 100) }; }
    
    if (!response.ok) {
      return NextResponse.json({ error: data.detail || data.error || 'Backend failed to ingest' }, { status: response.status });
    }
    return NextResponse.json(data);
  } catch (error) {
    return NextResponse.json({ error: 'Failed to connect to backend' }, { status: 500 });
  }
}
