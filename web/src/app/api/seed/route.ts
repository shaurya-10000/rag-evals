import { NextResponse } from 'next/server';

export async function POST() {
  const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://127.0.0.1:8000';

  const payload = {
    title: "Shaurya's Resume",
    text: "Shaurya is a Full-Stack & AI Engineer. He built a Python interpreter, an x86-64 compiler, and a production-grade RAG system with hybrid search and reranking.",
    source_url: "https://github.com/shaurya-10000"
  };

  try {
    const response = await fetch(backendUrl + '/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: 'Failed to seed database' }, { status: 500 });
  }
}
