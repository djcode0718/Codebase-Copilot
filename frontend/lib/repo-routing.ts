import type { Repo } from '@/lib/types';

export function isRepoWorkspaceReady(repo: Pick<Repo, 'status' | 'indexed_at' | 'file_count' | 'node_count'>): boolean {
  if (repo.status === 'ready') {
    return true;
  }

  // Treat repository as ready when completion metadata is present but status is stale.
  const hasIndexedAt = Boolean(repo.indexed_at);
  const hasFileCount = typeof repo.file_count === 'number' && repo.file_count >= 0;
  const hasNodeCount = typeof repo.node_count === 'number' && repo.node_count >= 0;

  return repo.status !== 'failed' && hasIndexedAt && (hasFileCount || hasNodeCount);
}

export function getRepoWorkspaceHref(repo: Pick<Repo, 'id' | 'status' | 'indexed_at' | 'file_count' | 'node_count'>): string {
  return isRepoWorkspaceReady(repo) ? `/repo/${repo.id}` : `/repo/${repo.id}/indexing`;
}

