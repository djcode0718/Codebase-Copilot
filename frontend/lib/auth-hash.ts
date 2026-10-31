/**
 * lib/auth-hash.ts — Pure utilities for handling URL hash authentication fragments,
 * redirect sanitization, and error message formatting.
 */

export interface ParsedAuthHash {
  accessToken?: string;
  refreshToken?: string;
  type?: string;
  error?: string;
  errorCode?: string;
  errorDescription?: string;
  hasTokens: boolean;
  hasError: boolean;
  isIncomplete: boolean;
}

/**
 * Validates and sanitizes a post-authentication redirect path to prevent open redirect vulnerabilities.
 * Only allows relative paths starting with a single '/' (blocking '//', '/\', and protocol schemes).
 */
export function sanitizeNextPath(next: string | null | undefined, fallback = '/dashboard'): string {
  if (!next || typeof next !== 'string') {
    return fallback;
  }
  const trimmed = next.trim();
  if (
    !trimmed.startsWith('/') ||
    trimmed.startsWith('//') ||
    trimmed.startsWith('/\\') ||
    trimmed.includes(':')
  ) {
    return fallback;
  }
  return trimmed;
}

/**
 * Parses URL hash fragments containing OAuth/Magic Link implicit grant tokens or errors.
 * Never logs or exposes token values.
 */
export function parseAuthHash(rawHash: string): ParsedAuthHash {
  if (!rawHash || typeof rawHash !== 'string') {
    return {
      hasTokens: false,
      hasError: false,
      isIncomplete: false,
    };
  }

  const hash = rawHash.startsWith('#') ? rawHash.slice(1) : rawHash;
  if (!hash.trim()) {
    return {
      hasTokens: false,
      hasError: false,
      isIncomplete: false,
    };
  }

  const params = new URLSearchParams(hash);
  const accessToken = params.get('access_token') || undefined;
  const refreshToken = params.get('refresh_token') || undefined;
  const type = params.get('type') || undefined;
  const error = params.get('error') || undefined;
  const errorCode = params.get('error_code') || undefined;
  const rawDesc = params.get('error_description') || undefined;
  const errorDescription = rawDesc ? decodeURIComponent(rawDesc.replace(/\+/g, ' ')) : undefined;

  const hasTokens = Boolean(accessToken && refreshToken);
  const isIncomplete = Boolean((accessToken && !refreshToken) || (!accessToken && refreshToken));
  const hasError = Boolean(error || errorCode || errorDescription);

  return {
    accessToken,
    refreshToken,
    type,
    error,
    errorCode,
    errorDescription,
    hasTokens,
    hasError,
    isIncomplete,
  };
}

/**
 * Removes sensitive URL hash fragments from the browser address bar without triggering navigation.
 */
export function clearUrlHash(): void {
  if (typeof window === 'undefined' || !window.location.hash) {
    return;
  }
  try {
    const cleanUrl = window.location.pathname + window.location.search;
    window.history.replaceState(null, '', cleanUrl);
  } catch {
    // Ignore history API access errors (e.g. sandboxed environments)
  }
}

/**
 * Maps Supabase URL fragment error codes to friendly, actionable user messages.
 */
export function getFriendlyAuthErrorMessage(parsed: ParsedAuthHash): string {
  if (parsed.isIncomplete) {
    return 'Invalid authentication link: missing required session tokens. Please request a new link.';
  }

  const code = (parsed.errorCode || '').toLowerCase();
  const desc = (parsed.errorDescription || '').toLowerCase();

  if (code === 'otp_expired' || desc.includes('expired')) {
    return 'This sign-in link has expired. Please request a new link to sign in.';
  }

  if (code === 'access_denied' || parsed.error === 'access_denied') {
    return parsed.errorDescription || 'Access was denied for this authentication link.';
  }

  if (parsed.errorDescription) {
    return parsed.errorDescription;
  }

  if (parsed.error) {
    return `Authentication failed: ${parsed.error}`;
  }

  return 'Authentication failed. The sign-in link may be invalid or expired.';
}
