// @vitest-environment jsdom
/**
 * auth-storage.test.ts
 * Tests for browser storage cleanup, user-scoped repository cache isolation,
 * and preference preservation.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
  REMEMBER_EMAIL_STORAGE_ID,
  AUTH_SIGNIN_MARKER_STORAGE_ID,
  LEGACY_REPOS_CACHE_KEY,
  USER_REPOS_CACHE_KEY_PREFIX,
  getUserReposCacheKey,
  clearAccountStorage,
} from './auth-storage';

describe('auth-storage utilities', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });

  it('generates consistent user-scoped cache keys', () => {
    expect(getUserReposCacheKey('user-123')).toBe('codebase-copilot.repos.cache.v2.user-123');
    expect(getUserReposCacheKey('user-456')).toBe('codebase-copilot.repos.cache.v2.user-456');
    expect(getUserReposCacheKey('user-123')).not.toBe(getUserReposCacheKey('user-456'));
  });

  it('clears legacy repository cache and all user-scoped caches on global logout', () => {
    localStorage.setItem(LEGACY_REPOS_CACHE_KEY, JSON.stringify([{ id: 'repo-old' }]));
    localStorage.setItem(getUserReposCacheKey('user-1'), JSON.stringify([{ id: 'repo-1' }]));
    localStorage.setItem(getUserReposCacheKey('user-2'), JSON.stringify([{ id: 'repo-2' }]));
    localStorage.setItem('codebase-sidebar-active-repo-id', 'repo-1');
    localStorage.setItem('codebase-sidebar-history-visibility-v1', '{"repo-1": true}');
    localStorage.setItem('chat_suggestions_repo-1', '["what is X?"]');
    localStorage.setItem('codebase:health-latest:repo-1', '{"score": 90}');
    localStorage.setItem('codebase:recent-files:repo-1', '["main.py"]');

    sessionStorage.setItem('codebase:open-chat-session:repo-1', 'chat-abc');
    sessionStorage.setItem('codebase:new-chat:repo-1', '1');

    clearAccountStorage();

    // Verify account and repo state is cleared
    expect(localStorage.getItem(LEGACY_REPOS_CACHE_KEY)).toBeNull();
    expect(localStorage.getItem(getUserReposCacheKey('user-1'))).toBeNull();
    expect(localStorage.getItem(getUserReposCacheKey('user-2'))).toBeNull();
    expect(localStorage.getItem('codebase-sidebar-active-repo-id')).toBeNull();
    expect(localStorage.getItem('codebase-sidebar-history-visibility-v1')).toBeNull();
    expect(localStorage.getItem('chat_suggestions_repo-1')).toBeNull();
    expect(localStorage.getItem('codebase:health-latest:repo-1')).toBeNull();
    expect(localStorage.getItem('codebase:recent-files:repo-1')).toBeNull();

    expect(sessionStorage.getItem('codebase:open-chat-session:repo-1')).toBeNull();
    expect(sessionStorage.getItem('codebase:new-chat:repo-1')).toBeNull();
  });

  it('preserves user preferences during storage cleanup', () => {
    localStorage.setItem('theme', 'dark');
    localStorage.setItem(REMEMBER_EMAIL_STORAGE_ID, 'user@example.com');
    localStorage.setItem(AUTH_SIGNIN_MARKER_STORAGE_ID, '1');
    localStorage.setItem('codebase-sidebar-collapsed', '1');
    localStorage.setItem(getUserReposCacheKey('user-1'), JSON.stringify([{ id: 'repo-1' }]));

    sessionStorage.setItem('unrelated-session-key', 'active');

    clearAccountStorage();

    // Preferences preserved
    expect(localStorage.getItem('theme')).toBe('dark');
    expect(localStorage.getItem(REMEMBER_EMAIL_STORAGE_ID)).toBe('user@example.com');
    expect(localStorage.getItem(AUTH_SIGNIN_MARKER_STORAGE_ID)).toBe('1');
    expect(localStorage.getItem('codebase-sidebar-collapsed')).toBe('1');
    expect(sessionStorage.getItem('unrelated-session-key')).toBe('active');

    // Account data removed
    expect(localStorage.getItem(getUserReposCacheKey('user-1'))).toBeNull();
  });

  it('clears only targeted user cache during user switch', () => {
    localStorage.setItem(getUserReposCacheKey('user-1'), JSON.stringify([{ id: 'repo-user1' }]));
    localStorage.setItem(getUserReposCacheKey('user-2'), JSON.stringify([{ id: 'repo-user2' }]));
    localStorage.setItem('codebase-sidebar-active-repo-id', 'repo-user1');

    clearAccountStorage('user-1');

    // user-1 removed
    expect(localStorage.getItem(getUserReposCacheKey('user-1'))).toBeNull();
    // user-2 preserved
    expect(localStorage.getItem(getUserReposCacheKey('user-2'))).not.toBeNull();
    // account-scoped sidebar reset
    expect(localStorage.getItem('codebase-sidebar-active-repo-id')).toBeNull();
  });

  it('handles storage access exceptions gracefully without throwing', () => {
    const originalRemoveItem = localStorage.removeItem;
    localStorage.removeItem = vi.fn().mockImplementation(() => {
      throw new Error('QuotaExceeded or SecurityError in sandboxed iframe');
    });

    expect(() => clearAccountStorage()).not.toThrow();

    localStorage.removeItem = originalRemoveItem;
  });

  it('is idempotent across multiple successive calls', () => {
    localStorage.setItem(getUserReposCacheKey('user-1'), JSON.stringify([{ id: 'repo-1' }]));
    clearAccountStorage();
    expect(() => clearAccountStorage()).not.toThrow();
    expect(() => clearAccountStorage()).not.toThrow();
    expect(localStorage.getItem(getUserReposCacheKey('user-1'))).toBeNull();
  });
});
