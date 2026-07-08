"use client";

import Link from "next/link";
import { useDeleteRepo, useRepos } from "@/hooks/use-repos";
import { StatusDot } from "@/components/repo/status-dot";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { toErrorMessage } from "@/lib/api/error-message";

export default function ReposPage() {
  const { data: repos, isLoading, error } = useRepos();
  const deleteRepo = useDeleteRepo();

  return (
    <section className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Repositories</h2>
        <Link href="/repos/new" className="rounded-md bg-[var(--accent)] px-3 py-1.5 text-sm text-white">
          Add repository
        </Link>
      </div>

      {isLoading ? <p className="text-sm text-[var(--text-secondary)]">Loading repositories...</p> : null}
      {error ? <p className="text-sm text-[var(--error)]">{toErrorMessage(error)}</p> : null}

      <div className="grid gap-3">
        {repos?.map((repo) => (
          <div key={repo.id} className="flex items-center justify-between rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
            <Link href={`/repos/${repo.id}`} className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <StatusDot status={repo.status} />
                <p className="truncate font-medium">{repo.name}</p>
              </div>
              <p className="mt-1 truncate text-xs text-[var(--text-secondary)]">{repo.source_url}</p>
            </Link>

            <ConfirmDialog
              title="Delete repository"
              description="This removes the repository, chats, and stored index data."
              confirmLabel="Delete"
              onConfirm={() => deleteRepo.mutateAsync(repo.id).then(() => Promise.resolve())}
              trigger={
                <button type="button" className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--error)]">
                  Delete
                </button>
              }
            />
          </div>
        ))}
      </div>
    </section>
  );
}
