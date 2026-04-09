import { NextRequest, NextResponse } from "next/server";

/**
 * Next.js middleware — runs on every request before rendering.
 *
 * Responsibilities:
 *  1. Redirect unauthenticated users away from protected routes.
 *  2. Redirect authenticated users away from auth pages.
 *
 * Note: actual JWT validation happens server-side in API routes / RSC.
 * This middleware does a lightweight heuristic check (no crypto).
 */

const PUBLIC_PATHS = new Set([
  "/login",
  "/register",
  "/forgot-password",
  "/verify-email",
]);

const STATIC_PREFIXES = ["/_next", "/favicon", "/api/health"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Skip static assets and Next.js internals
  if (STATIC_PREFIXES.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check for access token in Authorization header or cookie
  // (The actual token is in-memory JS; we use a lightweight session cookie
  //  to signal "has valid session" without exposing the JWT to middleware)
  const sessionCookie = request.cookies.get("catai_session");
  const isAuthenticated = !!sessionCookie?.value;

  const isPublicPath = PUBLIC_PATHS.has(pathname) || pathname === "/";

  // Unauthenticated user trying to access protected route
  if (!isAuthenticated && !isPublicPath) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("next", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Authenticated user trying to access login/register
  if (isAuthenticated && PUBLIC_PATHS.has(pathname)) {
    return NextResponse.redirect(new URL("/dashboard/chat", request.url));
  }

  // Pass through with security headers
  const response = NextResponse.next();
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("X-Content-Type-Options", "nosniff");

  return response;
}

export const config = {
  matcher: [
    /*
     * Match all paths except:
     * - _next/static (static files)
     * - _next/image (image optimization)
     * - favicon.ico
     * - public folder files
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|ico|webp)$).*)",
  ],
};