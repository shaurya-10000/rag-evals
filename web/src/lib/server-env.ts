const DEV_API_KEY = 'dev-secret-key-change-in-production';

/**
 * RAG_API_KEY for server-to-backend calls.
 * In production a missing key returns null instead of silently using the dev key.
 */
export function getApiKey(): string | null {
  const key = process.env.RAG_API_KEY;
  if (key) return key;
  return process.env.NODE_ENV === 'production' ? null : DEV_API_KEY;
}

/**
 * Base URL of the FastAPI backend, without a trailing slash.
 * Prefers a server-only BACKEND_URL, falls back to NEXT_PUBLIC_BACKEND_URL.
 * Only falls back to localhost outside production, so a missing env var
 * fails loudly on Vercel instead of silently pointing at 127.0.0.1.
 */
export function getBackendUrl(): string {
  const url = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;
  if (url) return url.replace(/\/+$/, '');
  if (process.env.NODE_ENV === 'production') {
    throw new Error('BACKEND_URL is not set');
  }
  return 'http://127.0.0.1:8000';
}