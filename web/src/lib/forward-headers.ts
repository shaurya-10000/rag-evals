/** Request id plus the visitor's real details, so the backend can log them and rate-limit per client. */
export function forwardHeaders(req: Request): Record<string, string> {
  const forwardedFor = req.headers.get('x-forwarded-for')?.split(',')[0]?.trim();
  const clientIp = forwardedFor || req.headers.get('x-real-ip') || '';
  const headers: Record<string, string> = {
    'X-Request-ID': crypto.randomUUID().replace(/-/g, '').slice(0, 16),
    'X-Client-User-Agent': req.headers.get('user-agent') ?? '',
  };
  if (clientIp) headers['X-Client-IP'] = clientIp;
  return headers;
}
