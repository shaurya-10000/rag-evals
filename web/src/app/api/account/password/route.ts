import { proxyAccount } from '@/lib/account-proxy';

export async function POST(req: Request) {
  return proxyAccount(req, '/account/password', 'POST', true);
}
