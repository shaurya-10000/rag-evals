import { getApiKey, getBackendUrl } from '../../../lib/server-env';
import { NextResponse } from 'next/server';

export async function POST(req: Request) {
  try {
    const { prompt } = await req.json();
    const backendUrl = getBackendUrl();
    const apiKey = getApiKey();
    if (!apiKey) {
      return NextResponse.json({ title: 'New Chat' }, { status: 200 });
    }

    const response = await fetch(`${backendUrl}/generate-title`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-API-Key': apiKey,
      },
      body: JSON.stringify({ prompt }),
    });

    if (!response.ok) {
      console.error("Backend title generation error:", response.status);
      return NextResponse.json({ title: "New Chat" }, { status: 200 });
    }

    const data = await response.json();
    return NextResponse.json({ title: data.title });
  } catch (error) {
    console.error("Title proxy error:", error);
    return NextResponse.json({ title: "New Chat" }, { status: 200 });
  }
}
