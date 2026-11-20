import { proxyAccount } from '@/lib/account-proxy';

export async function POST(req: Request) {
  return proxyAccount(req, '/account/delete', 'POST', true);
}
