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

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

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
  const res = await fetch(`${API_BASE}/api/repo/index`, {
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
  const res = await fetch(`${API_BASE}/api/repo/list`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list repositories');
  return res.json();
}

/** GET /api/repo/{repo_id} — single repo status */
export async function getRepo(token: string, repoId: string): Promise<Repo> {
  const res = await fetch(`${API_BASE}/api/repo/${repoId}`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Repository not found');
  return res.json();
}

/** DELETE /api/repo/{repo_id} */
export async function deleteRepo(token: string, repoId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/repo/${repoId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete repository');
}

/** Returns the URL for the indexing SSE stream — open with EventSource or fetch */
export function indexProgressUrl(repoId: string): string {
  return `${API_BASE}/api/repo/${repoId}/index-progress`;
}

// ── Chat endpoints ────────────────────────────────────────────────────────

/** POST /api/chat/session — create a new chat session */
export async function createChatSession(
  token: string,
  repoId: string
): Promise<CreateSessionResponse> {
  const res = await fetch(`${API_BASE}/api/chat/session`, {
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
  const res = await fetch(`${API_BASE}/api/chat/list?repo_id=${repoId}`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list chats');
  return res.json();
}

/** GET /api/chat/{chat_id}/messages — full message history */
export async function getMessages(token: string, chatId: string): Promise<Message[]> {
  const res = await fetch(`${API_BASE}/api/chat/${chatId}/messages`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load messages');
  return res.json();
}

/** DELETE /api/chat/{chat_id} */
export async function deleteChat(token: string, chatId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat/${chatId}`, {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete chat');
}

/** Returns the URL for chat streaming — POST with fetch, read as SSE */
export function chatStreamUrl(chatId: string): string {
  return `${API_BASE}/api/chat/${chatId}/message/stream`;
}

// ── Suggestions endpoint ──────────────────────────────────────────────────

/** GET /api/repo/{repo_id}/suggestions */
export async function getSuggestions(
  token: string,
  repoId: string
): Promise<SuggestionsResponse> {
  const res = await fetch(`${API_BASE}/api/repo/${repoId}/suggestions`, {
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
  const res = await fetch(`${API_BASE}/api/eval/${repoId}/latest`, {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to get evaluation');
  const data = await res.json();
  return data ?? null;
}

/** POST /api/eval/run — starts eval SSE stream */
export function evalRunUrl(): string {
  return `${API_BASE}/api/eval/run`;
}

// ── Health ────────────────────────────────────────────────────────────────

export async function checkHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${API_BASE}/api/health`, { cache: 'no-store' });
    const data = await res.json();
    return data?.status === 'ok';
  } catch {
    return false;
  }
}
