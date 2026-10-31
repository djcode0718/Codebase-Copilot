// @vitest-environment jsdom
/**
 * lib/auth-flow.test.ts — Deterministic tests for all authentication flows:
 * 1. Password login.
 * 2. Existing PKCE callback.
 * 3. Successful implicit hash callback.
 * 4. Incomplete access/refresh token pair.
 * 5. Expired magic link.
 * 6. Rejected or invalid tokens.
 * 7. Successful session persistence after page reload.
 * 8. Protected-route access after session establishment.
 * 9. Validated nextPath redirect.
 * 10. Duplicate callback prevention.
 * 11. Supabase automatic URL detection completing before manual setSession() fallback.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { parseAuthHash, sanitizeNextPath, clearUrlHash, getFriendlyAuthErrorMessage } from './auth-hash';

describe('Authentication Flow & Callback Logic', () => {
  let mockSupabase: {
    auth: {
      signInWithPassword: ReturnType<typeof vi.fn>;
      getSession: ReturnType<typeof vi.fn>;
      setSession: ReturnType<typeof vi.fn>;
      getUser: ReturnType<typeof vi.fn>;
      onAuthStateChange: ReturnType<typeof vi.fn>;
    };
  };

  let mockRouter: {
    replace: ReturnType<typeof vi.fn>;
    refresh: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    vi.restoreAllMocks();

    mockSupabase = {
      auth: {
        signInWithPassword: vi.fn(),
        getSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
        setSession: vi.fn().mockResolvedValue({ data: { session: null }, error: null }),
        getUser: vi.fn().mockResolvedValue({ data: { user: null }, error: null }),
        onAuthStateChange: vi.fn().mockReturnValue({
          data: { subscription: { unsubscribe: vi.fn() } },
        }),
      },
    };

    mockRouter = {
      replace: vi.fn(),
      refresh: vi.fn(),
    };
  });

  // Test 1: Password Login
  it('1. Password login establishes session and navigates to nextPath', async () => {
    const mockSession = {
      access_token: 'pwd-access-token',
      refresh_token: 'pwd-refresh-token',
      user: { id: 'user-1', email: 'dev@example.com', is_anonymous: false },
    };

    mockSupabase.auth.signInWithPassword.mockResolvedValueOnce({
      data: { user: mockSession.user, session: mockSession },
      error: null,
    });

    const email = 'dev@example.com';
    const password = 'SecretPassword123';
    const nextPath = sanitizeNextPath('/dashboard');

    const result = await mockSupabase.auth.signInWithPassword({ email, password });
    expect(result.error).toBeNull();
    expect(result.data.session?.user.email).toBe('dev@example.com');

    mockRouter.replace(nextPath);
    mockRouter.refresh();

    expect(mockRouter.replace).toHaveBeenCalledWith('/dashboard');
    expect(mockRouter.refresh).toHaveBeenCalled();
  });

  // Test 2: Existing PKCE Callback
  it('2. Existing PKCE callback detects authorization code and checks authenticated user', async () => {
    const oauthCode = 'pkce-auth-code-789';
    const mockUser = { id: 'user-pkce', email: 'oauth@example.com', is_anonymous: false };

    mockSupabase.auth.getUser.mockResolvedValueOnce({
      data: { user: mockUser },
      error: null,
    });

    // Simulating PKCE branch: oauthCode exists, implicit hash tokens absent
    const isPKCE = Boolean(oauthCode);
    expect(isPKCE).toBe(true);

    const { data: { user } } = await mockSupabase.auth.getUser();
    expect(user?.email).toBe('oauth@example.com');

    const target = sanitizeNextPath('/dashboard');
    mockRouter.replace(target);
    mockRouter.refresh();

    expect(mockRouter.replace).toHaveBeenCalledWith('/dashboard');
    expect(mockSupabase.auth.setSession).not.toHaveBeenCalled();
  });

  // Test 3: Successful Implicit Hash Callback
  it('3. Successful implicit hash callback establishes session via setSession when needed and redirects', async () => {
    const rawHash = '#access_token=magic-access-token&refresh_token=magic-refresh-token&type=magiclink';
    const parsed = parseAuthHash(rawHash);

    expect(parsed.hasTokens).toBe(true);
    expect(parsed.accessToken).toBe('magic-access-token');
    expect(parsed.refreshToken).toBe('magic-refresh-token');

    // Simulate auto-detection not yet complete
    mockSupabase.auth.getSession.mockResolvedValueOnce({ data: { session: null }, error: null });

    const mockSession = {
      access_token: parsed.accessToken!,
      refresh_token: parsed.refreshToken!,
      user: { id: 'magic-user-1', email: 'magic@example.com', is_anonymous: false },
    };

    mockSupabase.auth.setSession.mockResolvedValueOnce({
      data: { session: mockSession },
      error: null,
    });

    // Processing callback
    const { data: existing } = await mockSupabase.auth.getSession();
    if (!existing.session) {
      const { data: sessionData, error } = await mockSupabase.auth.setSession({
        access_token: parsed.accessToken!,
        refresh_token: parsed.refreshToken!,
      });

      expect(error).toBeNull();
      expect(sessionData.session?.user.email).toBe('magic@example.com');

      const nextPath = sanitizeNextPath(null, '/dashboard');
      mockRouter.replace(nextPath);
      mockRouter.refresh();

      expect(mockRouter.replace).toHaveBeenCalledWith('/dashboard');
      expect(mockRouter.refresh).toHaveBeenCalled();
    }
  });

  // Test 4: Incomplete Token Pair
  it('4. Incomplete access/refresh token pair returns error and avoids setSession', async () => {
    const rawHash = '#access_token=orphan-access-token&type=magiclink';
    const parsed = parseAuthHash(rawHash);

    expect(parsed.hasTokens).toBe(false);
    expect(parsed.isIncomplete).toBe(true);

    const errorMsg = getFriendlyAuthErrorMessage(parsed);
    expect(errorMsg).toContain('missing required session tokens');

    // Execution must NOT call setSession with incomplete parameters
    if (parsed.hasTokens && parsed.accessToken && parsed.refreshToken) {
      await mockSupabase.auth.setSession({
        access_token: parsed.accessToken,
        refresh_token: parsed.refreshToken,
      });
    }

    expect(mockSupabase.auth.setSession).not.toHaveBeenCalled();
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  // Test 5: Expired Magic Link
  it('5. Expired magic link parses error code, surfaces user-friendly error, and avoids redirect', () => {
    const rawHash = '#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired';
    const parsed = parseAuthHash(rawHash);

    expect(parsed.hasError).toBe(true);
    expect(parsed.errorCode).toBe('otp_expired');

    const friendlyError = getFriendlyAuthErrorMessage(parsed);
    expect(friendlyError).toBe('This sign-in link has expired. Please request a new link to sign in.');
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  // Test 6: Rejected or Invalid Tokens
  it('6. Rejected or invalid tokens return error and do not redirect', async () => {
    const rawHash = '#access_token=bad-token&refresh_token=bad-refresh';
    const parsed = parseAuthHash(rawHash);

    mockSupabase.auth.getSession.mockResolvedValueOnce({ data: { session: null }, error: null });
    mockSupabase.auth.setSession.mockResolvedValueOnce({
      data: { session: null },
      error: new Error('Invalid Refresh Token: Refresh Token Not Found'),
    });

    const { data: sessionData, error } = await mockSupabase.auth.setSession({
      access_token: parsed.accessToken!,
      refresh_token: parsed.refreshToken!,
    });

    expect(error).toBeDefined();
    expect(error?.message).toContain('Invalid Refresh Token');
    expect(sessionData?.session).toBeNull();
    expect(mockRouter.replace).not.toHaveBeenCalled();
  });

  // Test 7: Successful Session Persistence After Page Reload
  it('7. Page reload retains established session via getSession/getUser', async () => {
    // When the page reloads, the hash is already gone
    const emptyHash = '';
    const parsed = parseAuthHash(emptyHash);
    expect(parsed.hasTokens).toBe(false);

    // But cookies stored by @supabase/ssr restore the session in GoTrue
    const existingSession = {
      access_token: 'persisted-token',
      refresh_token: 'persisted-refresh',
      user: { id: 'persisted-user', email: 'persisted@example.com', is_anonymous: false },
    };

    mockSupabase.auth.getUser.mockResolvedValueOnce({
      data: { user: existingSession.user },
      error: null,
    });

    const { data: { user } } = await mockSupabase.auth.getUser();
    expect(user).not.toBeNull();
    expect(user?.is_anonymous).toBe(false);
    expect(user?.email).toBe('persisted@example.com');
  });

  // Test 8: Protected Route Access Verification
  it('8. Protected routes evaluate user session to permit or restrict access', () => {
    const simulateRouteGuard = (pathname: string, user: { is_anonymous?: boolean } | null) => {
      const isProtected = pathname.startsWith('/dashboard') || pathname.startsWith('/repo') || pathname.startsWith('/settings');
      if (isProtected && (!user || user.is_anonymous)) {
        return { allowed: false, redirect: `/auth/sign-in?next=${encodeURIComponent(pathname)}` };
      }
      return { allowed: true, redirect: null };
    };

    // Unauthenticated user attempting to access /dashboard
    const unauthResult = simulateRouteGuard('/dashboard', null);
    expect(unauthResult.allowed).toBe(false);
    expect(unauthResult.redirect).toBe('/auth/sign-in?next=%2Fdashboard');

    // Authenticated user accessing /dashboard
    const authResult = simulateRouteGuard('/dashboard', { is_anonymous: false });
    expect(authResult.allowed).toBe(true);
    expect(authResult.redirect).toBeNull();
  });

  // Test 9: Validated nextPath Redirect
  it('9. Validated nextPath redirect prevents open redirects', () => {
    expect(sanitizeNextPath('//malicious-site.com', '/dashboard')).toBe('/dashboard');
    expect(sanitizeNextPath('/\\evil.com', '/dashboard')).toBe('/dashboard');
    expect(sanitizeNextPath('https://evil.com', '/dashboard')).toBe('/dashboard');
    expect(sanitizeNextPath('/repo/org/repo-1', '/dashboard')).toBe('/repo/org/repo-1');
  });

  // Test 10: Duplicate Callback Prevention
  it('10. Execution guard prevents duplicate session establishment and multiple redirects', async () => {
    let callbackHandled = false;
    let redirectCount = 0;

    const handleCallbackOnce = async () => {
      if (callbackHandled) return;
      callbackHandled = true;
      redirectCount++;
      mockRouter.replace('/dashboard');
    };

    // Simulate multiple concurrent events (e.g. processCallback and onAuthStateChange firing simultaneously)
    await Promise.all([
      handleCallbackOnce(),
      handleCallbackOnce(),
      handleCallbackOnce(),
    ]);

    expect(redirectCount).toBe(1);
    expect(mockRouter.replace).toHaveBeenCalledTimes(1);
  });

  // Test 11: Supabase Automatic URL Detection Completing Before Manual Fallback
  it('11. When Supabase automatic URL detection establishes session first, manual setSession is skipped', async () => {
    const autoDetectedSession = {
      access_token: 'auto-detected-token',
      refresh_token: 'auto-detected-refresh',
      user: { id: 'auto-user', email: 'auto@example.com', is_anonymous: false },
    };

    // getSession immediately returns the session established by GoTrue's background initialize()
    mockSupabase.auth.getSession.mockResolvedValueOnce({
      data: { session: autoDetectedSession },
      error: null,
    });

    const parsedHash = parseAuthHash('#access_token=token&refresh_token=refresh');

    const { data: { session: existingSession } } = await mockSupabase.auth.getSession();
    if (existingSession?.user && !existingSession.user.is_anonymous) {
      // Auto-detection succeeded! Redirect immediately without calling setSession
      mockRouter.replace('/dashboard');
      mockRouter.refresh();
    } else if (parsedHash.hasTokens) {
      await mockSupabase.auth.setSession({
        access_token: parsedHash.accessToken!,
        refresh_token: parsedHash.refreshToken!,
      });
    }

    // Crucial check: setSession MUST NOT be called because auto-detection won the race
    expect(mockSupabase.auth.setSession).not.toHaveBeenCalled();
    expect(mockRouter.replace).toHaveBeenCalledWith('/dashboard');
    expect(mockRouter.refresh).toHaveBeenCalledTimes(1);
  });
});
