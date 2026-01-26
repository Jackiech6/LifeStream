import { NextResponse } from 'next/server';
import type { NextRequest } from 'next/server';

// Minimal middleware so Next.js generates middleware-manifest.json at build time.
// Without this file, next start can fail with MODULE_NOT_FOUND for middleware-manifest.json.
export function middleware(_req: NextRequest) {
  return NextResponse.next();
}
