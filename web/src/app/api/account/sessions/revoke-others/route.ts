import { proxyAccount } from '@/lib/account-proxy';

export async function POST(req: Request) {
  return proxyAccount(req, '/account/sessions/revoke-others', 'POST');
}
