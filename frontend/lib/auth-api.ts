import { getApiBaseUrl } from '@/lib/api';

export type RegisterPreflightResult = {
  ok: boolean;
  message: string;
  email: string;
  providers: string[];
};

export type LoginPreflightResult = {
  ok: boolean;
  message: string;
  email: string;
  providers: string[];
  locked_until?: string | null;
};

function authUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

async function postJson<T>(path: string, body: unknown, token?: string): Promise<T> {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(authUrl(path), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'Authentication request failed.';
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

export function normalizeEmail(email: string): string {
  return email.trim().toLowerCase();
}

export async function preflightRegister(email: string, password: string): Promise<RegisterPreflightResult> {
  return postJson<RegisterPreflightResult>('/api/auth/register/preflight', { email: normalizeEmail(email), password });
}

export async function preflightLogin(email: string): Promise<LoginPreflightResult> {
  return postJson<LoginPreflightResult>('/api/auth/login/preflight', { email: normalizeEmail(email) });
}

export async function auditLoginAttempt(args: {
  email: string;
  success: boolean;
  provider: 'password' | 'github' | 'google' | 'azure' | 'anonymous' | 'other';
  token?: string;
  failureReason?: string;
  rememberMe?: boolean;
  sessionId?: string;
  metadata?: Record<string, unknown>;
}): Promise<void> {
  await postJson('/api/auth/login/audit', {
    email: normalizeEmail(args.email),
    success: args.success,
    provider: args.provider,
    failure_reason: args.failureReason,
    remember_me: args.rememberMe,
    session_id: args.sessionId,
    metadata: args.metadata ?? {},
  }, args.token);
}

export async function auditLogout(args: {
  token?: string;
  email?: string;
  sessionId?: string;
  allDevices?: boolean;
}): Promise<void> {
  await postJson('/api/auth/logout/audit', {
    email: args.email ? normalizeEmail(args.email) : undefined,
    session_id: args.sessionId,
    all_devices: Boolean(args.allDevices),
  }, args.token);
}

export async function auditPasswordResetRequest(email: string): Promise<void> {
  await postJson('/api/auth/password-reset/audit-request', { email: normalizeEmail(email) });
}

export async function auditPasswordResetComplete(args: {
  token?: string;
  email?: string;
  success?: boolean;
}): Promise<void> {
  await postJson('/api/auth/password-reset/audit-complete', {
    email: args.email ? normalizeEmail(args.email) : undefined,
    success: args.success !== false,
  }, args.token);
}

export async function linkOAuthIdentity(token: string, provider?: string): Promise<void> {
  await postJson('/api/auth/oauth/link', { provider }, token);
}

export async function getSessionHistory(token: string, limit = 20): Promise<Array<{
  id: string;
  provider: string;
  success: boolean;
  login_at?: string;
  logout_at?: string;
  browser?: string;
  os?: string;
  device?: string;
  ip_address?: string;
}>> {
  const res = await fetch(authUrl(`/api/auth/sessions?limit=${Math.max(1, Math.min(limit, 100))}`), {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  });
  if (!res.ok) {
    const payload = await res.json().catch(() => ({}));
    const detail = typeof payload?.detail === 'string' ? payload.detail : 'Failed to load sessions.';
    throw new Error(detail);
  }
  const payload = await res.json().catch(() => ({ sessions: [] }));
  return Array.isArray(payload?.sessions) ? payload.sessions : [];
}
