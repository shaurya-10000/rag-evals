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