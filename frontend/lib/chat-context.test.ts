/** @vitest-environment jsdom */

import { beforeEach, describe, expect, it } from 'vitest';
import {
  consumeExplorerFocus,
  consumeQueuedChatContext,
  queueChatContext,
  queueExplorerFocus,
} from './chat-context';

describe('chat context storage helpers', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('queues and consumes chat context once', () => {
    queueChatContext('repo-1', 'Explain this file', {
      repo_id: 'repo-1',
      selected_file: 'api/routers/chat.py',
      selected_symbol: 'create_session',
    });

    const consumed = consumeQueuedChatContext('repo-1');
    expect(consumed).toEqual({
      repo_id: 'repo-1',
      selected_file: 'api/routers/chat.py',
      selected_symbol: 'create_session',
    });

    const consumedAgain = consumeQueuedChatContext('repo-1');
    expect(consumedAgain).toBeNull();
  });

  it('stores explorer focus with line range and consumes once', () => {
    queueExplorerFocus('repo-2', {
      path: 'frontend/app/repo/[id]/chat/page.tsx',
      line_start: 120,
      line_end: 126,
      source: 'chat_context_action',
    });

    const consumed = consumeExplorerFocus('repo-2');
    expect(consumed).toEqual({
      path: 'frontend/app/repo/[id]/chat/page.tsx',
      line_start: 120,
      line_end: 126,
      source: 'chat_context_action',
    });

    expect(consumeExplorerFocus('repo-2')).toBeNull();
  });

  it('ignores invalid explorer focus payload with empty path', () => {
    queueExplorerFocus('repo-3', { path: '   ' });
    expect(consumeExplorerFocus('repo-3')).toBeNull();
  });
});
