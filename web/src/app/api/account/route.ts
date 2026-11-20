import { proxyAccount } from '@/lib/account-proxy';

export async function GET(req: Request) {
  return proxyAccount(req, '/account', 'GET');
}
