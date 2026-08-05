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
  HealthCategoryDetailResponse,
  HealthHistoryResponse,
  HealthLatestResponse,
  HealthRun,
  ReviewFixResponse,
  ReviewListResponse,
  ReviewRun,
  SuggestionsResponse,
  ChatSearchResponse,
  ConversationSummary,
  MemoryExportResponse,
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
  repoId: string,
  sessionType: 'main' | 'quick_ask' = 'quick_ask'
): Promise<CreateSessionResponse> {
  const res = await fetch(apiUrl('/api/chat/session'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ repo_id: repoId, session_type: sessionType }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to create chat session');
  }
  return res.json();
}

export async function createQuickAskSession(token: string, repoId: string): Promise<CreateSessionResponse> {
  const res = await fetch(apiUrl('/api/chat/session/quick-ask'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ repo_id: repoId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to create quick ask session');
  }
  return res.json();
}

export async function createMainSession(token: string, repoId: string): Promise<CreateSessionResponse> {
  const res = await fetch(apiUrl('/api/chat/session/main'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ repo_id: repoId }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to load main session');
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

export async function listChatSessions(
  token: string,
  repoId: string,
  opts?: { includeArchived?: boolean; includeDeleted?: boolean; limit?: number; offset?: number; search?: string }
): Promise<Chat[]> {
  const params = new URLSearchParams({ repo_id: repoId });
  if (opts?.includeArchived !== undefined) params.set('include_archived', String(opts.includeArchived));
  if (opts?.includeDeleted !== undefined) params.set('include_deleted', String(opts.includeDeleted));
  if (opts?.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts?.offset !== undefined) params.set('offset', String(opts.offset));
  if (opts?.search) params.set('search', opts.search);

  const res = await fetch(apiUrl(`/api/chat/sessions?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list sessions');
  return res.json();
}

export async function updateChatSession(
  token: string,
  chatId: string,
  payload: Partial<Pick<Chat, 'title' | 'is_pinned' | 'is_favorite' | 'is_archived'>>
): Promise<Chat> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}`), {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to update chat session');
  return res.json();
}

export async function restoreChat(token: string, chatId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}/restore`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to restore chat');
}

export async function deleteAllChats(token: string, repoId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/chat/repo/${repoId}/all`), {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete all chats');
}

export async function deleteSelectedChats(token: string, repoId: string, chatIds: string[]): Promise<void> {
  const params = new URLSearchParams({ repo_id: repoId });
  const res = await fetch(apiUrl(`/api/chat/batch?${params.toString()}`), {
    method: 'DELETE',
    headers: authHeaders(token),
    body: JSON.stringify({ chat_ids: chatIds }),
  });
  if (!res.ok) throw new Error('Failed to delete selected chats');
}

export async function searchChats(token: string, repoId: string, query: string): Promise<ChatSearchResponse> {
  const params = new URLSearchParams({ repo_id: repoId, q: query });
  const res = await fetch(apiUrl(`/api/chat/search?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to search chats');
  return res.json();
}

export async function getConversationSummary(token: string, chatId: string): Promise<ConversationSummary> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}/summary`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load conversation summary');
  return res.json();
}

export async function regenerateConversationSummary(token: string, chatId: string): Promise<ConversationSummary> {
  const res = await fetch(apiUrl(`/api/chat/${chatId}/summary/regenerate`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to regenerate summary');
  return res.json();
}

export async function exportRepositoryMemory(
  token: string,
  repoId: string,
  format: 'md' | 'txt' | 'json' | 'pdf' | 'docx',
  chatIds?: string[]
): Promise<MemoryExportResponse> {
  const params = new URLSearchParams({ repo_id: repoId, format });
  if (chatIds && chatIds.length > 0) params.set('chat_ids', chatIds.join(','));
  const res = await fetch(apiUrl(`/api/chat/export?${params.toString()}`), {
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to export repository memory');
  return res.json();
}

/** GET /api/chat/{chat_id}/messages — full message history */
export async function getMessages(token: string, chatId: string, opts?: { limit?: number; offset?: number }): Promise<Message[]> {
  const params = new URLSearchParams();
  if (opts?.limit !== undefined) params.set('limit', String(opts.limit));
  if (opts?.offset !== undefined) params.set('offset', String(opts.offset));
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(apiUrl(`/api/chat/${chatId}/messages${suffix}`), {
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

// -- Repository Health Intelligence ------------------------------------------

/** POST /api/repo/{repo_id}/health/run */
export async function runRepositoryHealthAnalysis(
  token: string,
  repoId: string
): Promise<HealthRun> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/health/run`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to run repository health analysis');
  }
  return res.json();
}

/** GET /api/repo/{repo_id}/health/latest */
export async function getLatestRepositoryHealth(
  token: string,
  repoId: string
): Promise<HealthLatestResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/health/latest`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load repository health intelligence');
  return res.json();
}

/** GET /api/repo/{repo_id}/health/history */
export async function getRepositoryHealthHistory(
  token: string,
  repoId: string,
  days = 30,
  limit = 30
): Promise<HealthHistoryResponse> {
  const params = new URLSearchParams({ days: String(days), limit: String(limit) });
  const res = await fetch(apiUrl(`/api/repo/${repoId}/health/history?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load repository health history');
  return res.json();
}

/** GET /api/repo/{repo_id}/health/categories/{category} */
export async function getRepositoryHealthCategoryDetails(
  token: string,
  repoId: string,
  category: string,
  runId?: string
): Promise<HealthCategoryDetailResponse> {
  const params = new URLSearchParams();
  if (runId) params.set('run_id', runId);
  const suffix = params.toString() ? `?${params.toString()}` : '';

  const res = await fetch(apiUrl(`/api/repo/${repoId}/health/categories/${encodeURIComponent(category)}${suffix}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load category details');
  return res.json();
}

// -- AI Engineering Review -----------------------------------------------------

export async function reviewFile(
  token: string,
  payload: { repo_id: string; filename: string; prompt?: string }
): Promise<ReviewRun> {
  const res = await fetch(apiUrl('/api/reviews/file'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to review file');
  }
  return res.json();
}

export async function reviewFiles(
  token: string,
  payload: { repo_id: string; files: string[]; prompt?: string }
): Promise<ReviewRun> {
  const res = await fetch(apiUrl('/api/reviews/files'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to review files');
  }
  return res.json();
}

export async function reviewCommit(
  token: string,
  payload: { repo_id: string; commit_hash: string; prompt?: string }
): Promise<ReviewRun> {
  const res = await fetch(apiUrl('/api/reviews/commit'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to review commit');
  }
  return res.json();
}

export async function reviewPullRequest(
  token: string,
  payload: { repo_id: string; changed_files: string[]; diff: string; prompt?: string }
): Promise<ReviewRun> {
  const res = await fetch(apiUrl('/api/reviews/pr'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to review pull request');
  }
  return res.json();
}

export async function generateReviewFix(
  token: string,
  payload: { review_id: string; finding_id?: string; finding?: string; file?: string; code_area?: string }
): Promise<ReviewFixResponse> {
  const res = await fetch(apiUrl('/api/reviews/fix'), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to generate fix');
  }
  return res.json();
}

export async function listReviews(
  token: string,
  repoId: string,
  limit = 50
): Promise<ReviewListResponse> {
  const params = new URLSearchParams({ repo_id: repoId, limit: String(limit) });
  const res = await fetch(apiUrl(`/api/reviews?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to list reviews');
  return res.json();
}

export async function getReview(token: string, reviewId: string): Promise<ReviewRun> {
  const res = await fetch(apiUrl(`/api/reviews/${reviewId}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load review');
  return res.json();
}

export async function deleteReview(token: string, reviewId: string): Promise<void> {
  const res = await fetch(apiUrl(`/api/reviews/${reviewId}`), {
    method: 'DELETE',
    headers: authHeaders(token),
  });
  if (!res.ok) throw new Error('Failed to delete review');
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
