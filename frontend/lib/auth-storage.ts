export const REMEMBER_EMAIL_STORAGE_ID = 'codebase-copilot.remember-email.v1';
export const AUTH_SIGNIN_MARKER_STORAGE_ID = 'codebase-copilot.auth.just-signed-in';

export const LEGACY_REPOS_CACHE_KEY = 'codebase-copilot.repos.cache.v1';
export const USER_REPOS_CACHE_KEY_PREFIX = 'codebase-copilot.repos.cache.v2.';

export function getUserReposCacheKey(userId: string): string {
  return `${USER_REPOS_CACHE_KEY_PREFIX}${userId}`;
}

/**
 * Clears account-specific and repository-specific state from browser storage
 * (localStorage and sessionStorage) while preserving user preferences
 * (e.g., theme, remember-email, sidebar-collapsed).
 */
export function clearAccountStorage(targetUserId?: string): void {
  if (typeof window === 'undefined') return;

  // 1. Remove legacy global repository cache
  try {
    window.localStorage.removeItem(LEGACY_REPOS_CACHE_KEY);
  } catch {
    // Ignore storage errors in restricted contexts
  }

  // 2. Remove user-scoped repository caches and account-specific items from localStorage
  try {
    const keysToRemove: string[] = [];
    for (let i = 0; i < window.localStorage.length; i++) {
      const key = window.localStorage.key(i);
      if (!key) continue;

      if (targetUserId) {
        if (key === getUserReposCacheKey(targetUserId)) {
          keysToRemove.push(key);
        }
      } else if (key.startsWith(USER_REPOS_CACHE_KEY_PREFIX)) {
        keysToRemove.push(key);
      }

      if (
        key === 'codebase-sidebar-active-repo-id' ||
        key === 'codebase-sidebar-history-visibility-v1' ||
        key.startsWith('chat_suggestions_') ||
        key.startsWith('codebase:health-latest:') ||
        key.startsWith('codebase:health-history:') ||
        key.startsWith('codebase:recent-files:') ||
        key.startsWith('codebase:expanded-dirs:')
      ) {
        keysToRemove.push(key);
      }
    }

    for (const key of keysToRemove) {
      window.localStorage.removeItem(key);
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }

  // 3. Remove repo- and chat-specific keys from sessionStorage
  try {
    const sessionKeysToRemove: string[] = [];
    for (let i = 0; i < window.sessionStorage.length; i++) {
      const key = window.sessionStorage.key(i);
      if (!key) continue;

      if (key.startsWith('codebase:')) {
        sessionKeysToRemove.push(key);
      }
    }

    for (const key of sessionKeysToRemove) {
      window.sessionStorage.removeItem(key);
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
}
