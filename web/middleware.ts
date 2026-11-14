import { NextRequest, NextResponse } from 'next/server';

export async function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;
  
  // 1. Allow auth pages and API routes to pass through
  if (pathname.startsWith('/sign-in') || pathname.startsWith('/sign-up') || pathname.startsWith('/api/auth')) {
    return NextResponse.next();
  }
  
  // 2. Check if the auth cookie exists
  const token = req.cookies.get('access_token')?.value;
  
  // 3. If no token, redirect to login
  if (!token) {
    return NextResponse.redirect(new URL('/sign-in', req.url));
  }
  
  // 4. If token exists, let them in. 
  // The FastAPI backend will strictly verify the signature on every /query and /ingest request.
  return NextResponse.next();
}

export const config = {
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
