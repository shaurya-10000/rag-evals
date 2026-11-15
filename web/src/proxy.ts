import { jwtVerify } from 'jose';
import { NextRequest, NextResponse } from 'next/server';

const PUBLIC_PREFIXES = ['/sign-in', '/sign-up', '/api/auth'] as const;

function isPublicPath(pathname: string): boolean {
  return PUBLIC_PREFIXES.some((p) => pathname === p || pathname.startsWith(`${p}/`));
}

function redirectToSignIn(req: NextRequest): NextResponse {
  return NextResponse.redirect(new URL('/sign-in', req.url));
}

export async function proxy(req: NextRequest) {
  if (isPublicPath(req.nextUrl.pathname)) return NextResponse.next();

  const secret = process.env.JWT_SECRET;
  if (!secret) {
    console.error('proxy: JWT_SECRET is not set for this environment');
    return new NextResponse('Server misconfigured', { status: 500 });
  }

  const token = req.cookies.get('access_token')?.value;
  if (!token) return redirectToSignIn(req);

  try {
    await jwtVerify(token, new TextEncoder().encode(secret));
    return NextResponse.next();
  } catch {
    return redirectToSignIn(req);
  }
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};