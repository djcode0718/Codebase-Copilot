/**
 * lib/api.ts
 * Typed API client for the Codebase Copilot FastAPI backend.
 * All endpoints match the real backend contract verified from api/routers/*.py
 */
import type {
  Repo,
  BranchListResponse,
  BranchStatus,
  BranchActionResponse,
  BranchComparison,
  IndexRepoResponse,
  Chat,
  Message,
  CreateSessionResponse,
  EvalSummary,
  EvalHistoryResponse,
  EvalComparisonResponse,
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
  ExplorerTreeResponse,
  ExplorerFileDetails,
  ExplorerReviewResult,
  ExplorerFixProposal,
  ExplorerTestDiscoveryResult,
  ExplorerTestRunResult,
  ExplorerHistory,
  RecommendationLifecycleStatus,
} from './types';

const DEFAULT_API_BASE = 'http://localhost:8000';

export class ApiRequestError extends Error {
  status: number;
  detail: string;

  constructor(message: string, status: number, detail: string) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.detail = detail;
  }
}

async function buildApiRequestError(res: Response, fallbackMessage: string): Promise<ApiRequestError> {
  const err = await res.json().catch(() => ({ detail: res.statusText }));
  const detail = String(err?.detail || res.statusText || fallbackMessage);
  return new ApiRequestError(detail || fallbackMessage, res.status, detail);
}

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

export async function listRepoBranches(token: string, repoId: string, query = ''): Promise<BranchListResponse> {
  const params = new URLSearchParams();
  if (query.trim()) params.set('query', query.trim());
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches${suffix}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to load branches');
  }
  return res.json();
}

export async function refreshRepoBranches(token: string, repoId: string): Promise<BranchListResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/refresh`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to refresh branches');
  }
  return res.json();
}

export async function getRepoBranchStatus(token: string, repoId: string): Promise<BranchStatus> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/status`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to load branch status');
  }
  return res.json();
}

export async function checkoutRepoBranch(
  token: string,
  repoId: string,
  branch: string,
  pullLatest = true
): Promise<BranchActionResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/checkout`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ branch, pull_latest: pullLatest }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to checkout branch');
  }
  return res.json();
}

export async function pullRepoBranch(token: string, repoId: string, branch?: string): Promise<BranchActionResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/pull`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ branch }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to pull latest');
  }
  return res.json();
}

export async function returnRepoDefaultBranch(token: string, repoId: string): Promise<BranchActionResponse> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/return-default`), {
    method: 'POST',
    headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to return to default branch');
  }
  return res.json();
}

export async function compareRepoBranches(
  token: string,
  repoId: string,
  baseBranch: string,
  targetBranch: string
): Promise<BranchComparison> {
  const params = new URLSearchParams({ base_branch: baseBranch, target_branch: targetBranch });
  const res = await fetch(apiUrl(`/api/repo/${repoId}/branches/compare?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to compare branches');
  }
  return res.json();
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
  if (!res.ok) throw await buildApiRequestError(res, 'Failed to list sessions');
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
  const res = await fetch(apiUrl(`/api/chat/${chatId}?hard_delete=true`), {
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

/** PATCH /api/repo/{repo_id}/health/recommendations/{recommendation_id}/status */
export async function updateRepositoryHealthRecommendationStatus(
  token: string,
  repoId: string,
  recommendationId: string,
  status: RecommendationLifecycleStatus,
  reason?: string,
): Promise<{ recommendation_id: string; fingerprint: string; status: string; reason?: string; updated_at: string }> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/health/recommendations/${recommendationId}/status`), {
    method: 'PATCH',
    headers: authHeaders(token),
    body: JSON.stringify({ status, reason }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to update recommendation status');
  }
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
  payload: {
    review_id: string;
    repo_id?: string;
    finding_id?: string;
    finding?: string;
    file?: string;
    code_area?: string;
    recommendation?: string;
  }
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

// -- Repository Explorer ------------------------------------------------------

export async function getExplorerTree(
  token: string,
  repoId: string,
  options?: { path?: string; includeHidden?: boolean; limit?: number }
): Promise<ExplorerTreeResponse> {
  const params = new URLSearchParams();
  if (options?.path) params.set('path', options.path);
  if (options?.includeHidden !== undefined) params.set('include_hidden', String(options.includeHidden));
  if (options?.limit !== undefined) params.set('limit', String(options.limit));
  const suffix = params.toString() ? `?${params.toString()}` : '';
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/tree${suffix}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load repository tree');
  return res.json();
}

export async function getExplorerFile(token: string, repoId: string, path: string): Promise<ExplorerFileDetails> {
  const params = new URLSearchParams({ path });
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/file?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to open file');
  return res.json();
}

export async function runExplorerFileReview(
  token: string,
  repoId: string,
  payload: { path: string; review_type?: string; prompt?: string }
): Promise<ExplorerReviewResult> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/review/file`), {
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

export async function runExplorerBatchReview(
  token: string,
  repoId: string,
  payload: { paths: string[]; review_type?: string; prompt?: string }
): Promise<ExplorerReviewResult> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/review/files`), {
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

export async function generateExplorerFix(
  token: string,
  repoId: string,
  payload: { path: string; finding: string; recommendation?: string }
): Promise<ExplorerFixProposal> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/fix/generate`), {
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

export async function applyExplorerFix(
  token: string,
  repoId: string,
  payload: { fix_id: string; expected_sha256?: string; run_validation?: boolean }
): Promise<Record<string, unknown>> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/fix/apply`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to apply fix');
  }
  return res.json();
}

export async function discoverExplorerTests(
  token: string,
  repoId: string,
  paths: string[]
): Promise<ExplorerTestDiscoveryResult> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/tests/discover`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ paths }),
  });
  if (!res.ok) throw new Error('Failed to discover tests');
  return res.json();
}

export async function runExplorerTests(
  token: string,
  repoId: string,
  tests: string[],
  timeoutSeconds = 55
): Promise<ExplorerTestRunResult> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/tests/run`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify({ tests, timeout_seconds: timeoutSeconds }),
  });
  if (!res.ok) throw new Error('Failed to run tests');
  return res.json();
}

export async function getExplorerHistory(token: string, repoId: string, path: string): Promise<ExplorerHistory> {
  const params = new URLSearchParams({ path });
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/history?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load file history');
  return res.json();
}

export async function addExplorerConversationEntry(
  token: string,
  repoId: string,
  payload: { path: string; role: 'user' | 'assistant' | 'system'; content: string }
): Promise<Record<string, unknown>> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/explorer/conversations`), {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error('Failed to save conversation entry');
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

export interface RunEvalPayload {
  repo_id: string;
  index_name: string;
  mode?: 'quick' | 'standard' | 'deep' | 'benchmark';
  branch?: string;
  commit_sha?: string;
  embedding_version?: string;
  retrieval_settings?: Record<string, unknown>;
  prompt_version?: string;
  static_confidence_threshold?: number;
}

export async function getEvalHistory(
  token: string,
  repoId: string,
  limit = 30,
): Promise<EvalHistoryResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(apiUrl(`/api/eval/${repoId}/history?${params.toString()}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to load evaluation history');
  return res.json();
}

export async function compareEvals(
  token: string,
  repoId: string,
  options?: { currentEvalId?: string; baselineEvalId?: string },
): Promise<EvalComparisonResponse> {
  const params = new URLSearchParams();
  if (options?.currentEvalId) params.set('current_eval_id', options.currentEvalId);
  if (options?.baselineEvalId) params.set('baseline_eval_id', options.baselineEvalId);
  const query = params.toString();
  const res = await fetch(apiUrl(`/api/eval/${repoId}/compare${query ? `?${query}` : ''}`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (!res.ok) throw new Error('Failed to compare evaluations');
  return res.json();
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

// ── Relationship Graph ────────────────────────────────────────────────────

/** Thrown when the server responds with 404 — graph not found, not a network error. */
export class ApiNotFoundError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApiNotFoundError';
  }
}

/**
 * GET /api/repo/{repo_id}/relationship-graph
 * Full adjacency dict: { graph: { symbol: [ref_path, ...], ... } }
 * Throws ApiNotFoundError on 404, Error on other failures.
 */
export async function getRelationshipGraph(
  token: string,
  repoId: string
): Promise<import('./types').RelationshipGraph> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/relationship-graph`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (res.status === 404) {
    const err = await res.json().catch(() => ({ detail: 'Graph not found' }));
    throw new ApiNotFoundError(err.detail ?? 'Relationship graph not found for this repository.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to load relationship graph');
  }
  return res.json();
}

/**
 * GET /api/repo/{repo_id}/relationship-graph/keys
 * Lightweight symbol key list: { keys: ["symbol1", ...] }
 * Throws ApiNotFoundError on 404, Error on other failures.
 */
export async function getRelationshipGraphKeys(
  token: string,
  repoId: string
): Promise<import('./types').RelationshipGraphKeys> {
  const res = await fetch(apiUrl(`/api/repo/${repoId}/relationship-graph/keys`), {
    headers: authHeaders(token),
    cache: 'no-store',
  });
  if (res.status === 404) {
    const err = await res.json().catch(() => ({ detail: 'Graph not found' }));
    throw new ApiNotFoundError(err.detail ?? 'Relationship graph not found for this repository.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? 'Failed to load relationship graph keys');
  }
  return res.json();
}

