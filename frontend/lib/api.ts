/**
 * lib/api.ts
 * Typed API client for the Codebase Copilot FastAPI backend.
 * All endpoints match the real backend contract verified from api/routers/*.py
 */
import type {
  Repo,
  IndexRepoResponse,
  Chat,
  Message,
  CreateSessionResponse,
  EvalSummary,
  SuggestionsResponse,
} from './types';

const DEFAULT_API_BASE = 'http://localhost:8000';

function isPrivateIpv4(hostname: string): boolean {
  return /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.)/.test(hostname);
}

function isLoopbackHost(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname === '::1' ||
    hostname === '0.0.0.0' ||
    hostname === '[::1]'
  );
}

export function getApiBaseUrl(): string {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();

  if (typeof window === 'undefined') {
    return configured || DEFAULT_API_BASE;
  }

  if (configured) {
    try {
      const url = new URL(configured);
      const browserHost = window.location.hostname;

      // If we are on a different private-LAN host than the configured one,
      // trust the current browser host to avoid cross-device fetch failures.
      if (
        isPrivateIpv4(url.hostname) &&
        isPrivateIpv4(browserHost) &&
        url.hostname !== browserHost
      ) {
        return `${window.location.protocol}//${browserHost}:8000`;
      }

      // In local dev, stale host env values are common after network changes.
      if (
        window.location.port === '3000' &&
        !isLoopbackHost(browserHost) &&
        !isLoopbackHost(url.hostname) &&
        url.hostname !== browserHost
      ) {
        return `${window.location.protocol}//${browserHost}:8000`;
      }

      if (!isLoopbackHost(url.hostname)) {
        return configured.replace(/\/$/, '');
      }
    } catch {
      // Fall back to the current browser host below.
    }
  }

  return `${window.location.protocol}//${window.location.hostname}:8000`;
}

function apiUrl(path: string): string {
  return `${getApiBaseUrl()}${path}`;
}

// ── Auth header helper ────────────────────────────────────────────────────

export function authHeaders(token: string): HeadersInit {
  return {
    Authorization: `Bearer ${token}`,
    'Content-Type': 'application/json',
  };
}

// ── Repository endpoints ──────────────────────────────────────────────────

/** POST /api/repo/index — create repo record + returns repo_id for SSE stream */
export async function indexRepo(
  token: string,
  source: string
): Promise<IndexRepoResponse> {
  const res = await fetch(apiUrl('/api/repo/index'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ source }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to start indexing');
  }
  return res.json();
}

/** GET /api/repo/list — all repos for the current user */
export async function listRepos(token: string): Promise<Repo[]> {
  const res = await fetch(apiUrl('/api/repo/list'), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list repositories');
  return res.json();
}

/** GET /api/repo/{repo_id} — single repo status */
export async function getRepo(token: string, repoId: string): Promise<Repo> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Repository not found');
  return res.json();
}

/** DELETE /api/repo/{repo_id} */
export async function deleteRepo(token: string, repoId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}`), {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete repository');
}

/** POST /api/repo/{repo_id}/refresh — reset and re-index existing repo */
export async function refreshRepo(
  token: string,
  repoId: string
): Promise<IndexRepoResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/refresh`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to refresh repository');
  }
  return res.json();
}

/** Returns the URL for the indexing SSE stream — open with EventSource or fetch */
export function indexProgressUrl(repoId: string): string {
  return apiUrl(`/api/repo/${repoId}/index-progress`);
}

// ── Chat endpoints ────────────────────────────────────────────────────────

/** POST /api/chat/session — create a new chat session */
export async function createChatSession(
  token: string,
  repoId: string
): Promise<CreateSessionResponse> {
  const res = await fetch(apiUrl('/api/chat/session'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ repo_id: repoId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to create chat session');
  }
  return res.json();
}

/** GET /api/chat/list?repo_id=... — list chats for a repo */
export async function listChats(token: string, repoId: string): Promise<Chat[]> {
  const res = await fetch(apiUrl(`/api/chat/list?repo_id=${repoId}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list chats');
  return res.json();
}

/** GET /api/chat/{chat_id}/messages — full message history */
export async function getMessages(token: string, chatId: string): Promise<Message[]> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}/messages`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json();
}

/** DELETE /api/chat/{chat_id} */
export async function deleteChat(token: string, chatId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}`), {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete chat');
}

/** Returns the URL for chat streaming — POST with fetch, read as SSE */
export function chatStreamUrl(chatId: string): string {
  return apiUrl(`/api/chat/${chatId}/message/stream`);
}

// ── Suggestions endpoint ──────────────────────────────────────────────────

/** GET /api/repo/{repo_id}/suggestions */
export async function getSuggestions(
  token: string,
  repoId: string
): Promise<SuggestionsResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/suggestions`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to get suggestions');
  return res.json();
}

// ── Evaluation endpoints ──────────────────────────────────────────────────

/** GET /api/eval/{repo_id}/latest */
export async function getLatestEval(
  token: string,
  repoId: string
): Promise<EvalSummary | null> {
  const res = await fetch(apiUrl(`/api/eval/${repoId}/latest`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to get evaluation');
  const data = await res.json();
  return data ?? null;
}

/** POST /api/eval/run — starts eval SSE stream */
export function evalRunUrl(): string {
  return apiUrl('/api/eval/run');
}

// ── Health ────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(apiUrl('/api/health'), { cache: 'no-store' });
    const data = await res.json();
    return data?.status === 'ok';
  } catch {
    return false;
  }
}
