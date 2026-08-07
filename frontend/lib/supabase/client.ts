import { createBrowserClient } from '@supabase/ssr';

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export function createClient() {
  return createBrowserClient(SUPABASE_URL, SUPABASE_ANON_KEY);
}

export function buildOAuthRedirectUrl(nextPath: string, provider?: string): string {
  const origin = window.location.origin;
  const normalizedPath = nextPath.startsWith('/') ? nextPath : '/dashboard';
  const redirectUrl = new URL('/auth/sign-in', origin);
  redirectUrl.searchParams.set('next', normalizedPath);
  if (provider) {
    redirectUrl.searchParams.set('auth_provider', provider);
  }
  return redirectUrl.toString();
}
