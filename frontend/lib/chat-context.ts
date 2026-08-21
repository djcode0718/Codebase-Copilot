export type ChatContextScope = {
  repo_id: string;
  branch?: string;
  commit_sha?: string;
  selected_file?: string;
  selected_symbol?: string;
  selected_lines?: string;
  finding_id?: string;
  recommendation_id?: string;
  evidence_hint?: string;
};

const CONTEXT_KEY_PREFIX = 'codebase:chat-context:';
const PROMPT_KEY_PREFIX = 'codebase:preload-prompt:';

function contextKey(repoId: string): string {
  return `${CONTEXT_KEY_PREFIX}${repoId}`;
}

function promptKey(repoId: string): string {
  return `${PROMPT_KEY_PREFIX}${repoId}`;
}

export function queueChatContext(repoId: string, prompt: string, contextScope: ChatContextScope): void {
  if (typeof window === 'undefined') return;
  try {
    sessionStorage.setItem(promptKey(repoId), prompt);
    sessionStorage.setItem(contextKey(repoId), JSON.stringify(contextScope));
  } catch {
    // Ignore storage failures.
  }
}

export function consumeQueuedChatContext(repoId: string): ChatContextScope | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = sessionStorage.getItem(contextKey(repoId));
    if (!raw) return null;
    sessionStorage.removeItem(contextKey(repoId));
    const parsed = JSON.parse(raw) as ChatContextScope;
    if (!parsed || typeof parsed !== 'object') return null;
    return parsed;
  } catch {
    return null;
  }
}

