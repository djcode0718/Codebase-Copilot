import type { RepoStatusResponse } from "@/lib/types";
import { StatusDot } from "@/components/repo/status-dot";

export function RepoHeader({ repo }: { repo: RepoStatusResponse }) {
  return (
    <div className="rounded-lg border border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-4">
      <div className="flex items-center gap-2">
        <StatusDot status={repo.status} />
        <h2 className="text-lg font-semibold">{repo.name}</h2>
      </div>
      <div className="mt-3 grid gap-2 text-sm text-[var(--text-secondary)] md:grid-cols-2">
        <p>
          Source: {repo.source_url.startsWith("http") ? <a className="text-[var(--accent)]" href={repo.source_url} target="_blank" rel="noreferrer">{repo.source_url}</a> : repo.source_url}
        </p>
        <p>
          Index: <span className="font-mono">{repo.index_name}</span>
        </p>
        <p>Provider: {repo.llm_provider ?? "unknown"}</p>
        <p>Indexed at: {repo.indexed_at ? new Date(repo.indexed_at).toLocaleString() : "not indexed"}</p>
      </div>
    </div>
  );
}

