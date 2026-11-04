// @vitest-environment jsdom
/**
 * lib/auth-hash.test.ts — Unit tests for URL hash authentication parsing,
 * redirect sanitization, and error mapping.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  parseAuthHash,
  sanitizeNextPath,
  clearUrlHash,
  getFriendlyAuthErrorMessage,
} from './auth-hash';

describe('sanitizeNextPath', () => {
  it('returns fallback (/dashboard) when next path is missing or empty', () => {
    expect(sanitizeNextPath(null)).toBe('/dashboard');
    expect(sanitizeNextPath(undefined)).toBe('/dashboard');
    expect(sanitizeNextPath('')).toBe('/dashboard');
    expect(sanitizeNextPath('   ')).toBe('/dashboard');
  });

  it('allows safe relative paths', () => {
    expect(sanitizeNextPath('/settings')).toBe('/settings');
    expect(sanitizeNextPath('/repo/owner/name')).toBe('/repo/owner/name');
    expect(sanitizeNextPath('/dashboard?tab=overview')).toBe('/dashboard?tab=overview');
  });

  it('blocks open-redirect attempts with protocol-relative URLs', () => {
    expect(sanitizeNextPath('//attacker.com')).toBe('/dashboard');
    expect(sanitizeNextPath('//attacker.com/steal-token')).toBe('/dashboard');
  });

  it('blocks open-redirect attempts with backslash tricks', () => {
    expect(sanitizeNextPath('/\\attacker.com')).toBe('/dashboard');
    expect(sanitizeNextPath('/\\\\attacker.com')).toBe('/dashboard');
  });

  it('blocks full URLs and schema attempts', () => {
    expect(sanitizeNextPath('https://attacker.com')).toBe('/dashboard');
    expect(sanitizeNextPath('http://attacker.com')).toBe('/dashboard');
    expect(sanitizeNextPath('javascript:alert(1)')).toBe('/dashboard');
    expect(sanitizeNextPath('data:text/html,evil')).toBe('/dashboard');
  });

  it('respects a custom fallback if provided', () => {
    expect(sanitizeNextPath(null, '/repo')).toBe('/repo');
    expect(sanitizeNextPath('//evil.com', '/home')).toBe('/home');
  });
});

describe('parseAuthHash', () => {
  it('handles empty, null, or undefined hash inputs', () => {
    const emptyResult = parseAuthHash('');
    expect(emptyResult.hasTokens).toBe(false);
    expect(emptyResult.hasError).toBe(false);
    expect(emptyResult.isIncomplete).toBe(false);

    const nullResult = parseAuthHash(null as unknown as string);
    expect(nullResult.hasTokens).toBe(false);

    const hashOnly = parseAuthHash('#');
    expect(hashOnly.hasTokens).toBe(false);
  });

  it('extracts complete implicit magic link tokens', () => {
    const hash = '#access_token=mock-access-token-123&refresh_token=mock-refresh-token-456&token_type=bearer&type=magiclink&expires_in=3600';
    const parsed = parseAuthHash(hash);

    expect(parsed.hasTokens).toBe(true);
    expect(parsed.isIncomplete).toBe(false);
    expect(parsed.hasError).toBe(false);
    expect(parsed.accessToken).toBe('mock-access-token-123');
    expect(parsed.refreshToken).toBe('mock-refresh-token-456');
    expect(parsed.type).toBe('magiclink');
  });

  it('identifies incomplete token pairs with access_token only', () => {
    const hash = '#access_token=mock-access-token-only&type=magiclink';
    const parsed = parseAuthHash(hash);

    expect(parsed.hasTokens).toBe(false);
    expect(parsed.isIncomplete).toBe(true);
    expect(parsed.accessToken).toBe('mock-access-token-only');
    expect(parsed.refreshToken).toBeUndefined();
  });

  it('identifies incomplete token pairs with refresh_token only', () => {
    const hash = '#refresh_token=mock-refresh-token-only';
    const parsed = parseAuthHash(hash);

    expect(parsed.hasTokens).toBe(false);
    expect(parsed.isIncomplete).toBe(true);
    expect(parsed.refreshToken).toBe('mock-refresh-token-only');
    expect(parsed.accessToken).toBeUndefined();
  });

  it('correctly parses Supabase error fragments and decodes descriptions', () => {
    const hash = '#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired';
    const parsed = parseAuthHash(hash);

    expect(parsed.hasError).toBe(true);
    expect(parsed.hasTokens).toBe(false);
    expect(parsed.error).toBe('access_denied');
    expect(parsed.errorCode).toBe('otp_expired');
    expect(parsed.errorDescription).toBe('Email link is invalid or has expired');
  });

  it('handles percent-encoded error descriptions', () => {
    const hash = '#error=access_denied&error_description=Token%20has%20expired%20already';
    const parsed = parseAuthHash(hash);

    expect(parsed.hasError).toBe(true);
    expect(parsed.errorDescription).toBe('Token has expired already');
  });
});

describe('getFriendlyAuthErrorMessage', () => {
  it('returns appropriate message for incomplete credentials', () => {
    const parsed = parseAuthHash('#access_token=token-without-refresh');
    const message = getFriendlyAuthErrorMessage(parsed);
    expect(message).toContain('missing required session tokens');
  });

  it('maps otp_expired to an informative message', () => {
    const parsed = parseAuthHash('#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired');
    const message = getFriendlyAuthErrorMessage(parsed);
    expect(message).toBe('This sign-in link has expired. Please request a new link to sign in.');
  });

  it('falls back to errorDescription when provided', () => {
    const parsed = parseAuthHash('#error=access_denied&error_description=Custom+error+reason');
    const message = getFriendlyAuthErrorMessage(parsed);
    expect(message).toBe('Custom error reason');
  });

  it('provides a safe generic message when no description is present', () => {
    const parsed = parseAuthHash('#error=server_error');
    const message = getFriendlyAuthErrorMessage(parsed);
    expect(message).toBe('Authentication failed: server_error');
  });
});

describe('clearUrlHash', () => {
  beforeEach(() => {
    window.history.pushState(
      null,
      '',
      '/auth/sign-in?next=/dashboard#access_token=secret-token&refresh_token=secret-refresh'
    );
    vi.spyOn(window.history, 'replaceState').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('strips hash fragment without modifying pathname and searchParams', () => {
    clearUrlHash();

    expect(window.history.replaceState).toHaveBeenCalledWith(
      null,
      '',
      '/auth/sign-in?next=/dashboard'
    );
  });
});
