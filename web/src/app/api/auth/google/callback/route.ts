import { NextRequest, NextResponse } from 'next/server';
import { getBackendUrl } from '../../../../../lib/server-env';

// The backend redirects here with a one-time code. Exchange it for the session cookie,
// which has to be set on this (frontend) domain.
export async function GET(req: NextRequest) {
  const fail = () => NextResponse.redirect(new URL('/sign-in?error=google_failed', req.url));
  const code = req.nextUrl.searchParams.get('code');
  if (!code) return fail();

  try {
    const response = await fetch(getBackendUrl() + '/auth/oauth/exchange', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });
    if (!response.ok) return fail();

    const redirect = NextResponse.redirect(new URL('/', req.url));
    const setCookie = response.headers.get('set-cookie');
    if (setCookie) redirect.headers.set('set-cookie', setCookie);
    return redirect;
  } catch {
    return fail();
  }
}
