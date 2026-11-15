import { proxyAuth } from '../../../../lib/auth-proxy';

export async function POST(req: Request) {
  return proxyAuth(req, '/auth/resend-verification');
}
