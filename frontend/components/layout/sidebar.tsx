"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { Plus } from "lucide-react";
import { useRepos } from "@/hooks/use-repos";
import { StatusDot } from "@/components/repo/status-dot";

export function Sidebar() {
  const pathname = usePathname();
  const { data: repos, isLoading } = useRepos();

  return (
    <aside className="w-72 border-r border-[var(--border-subtle)] bg-[var(--bg-secondary)] p-3">
      <div className="mb-3 flex items-center justify-between">
        <h1 className="text-sm font-semibold text-[var(--text-primary)]">Codebase Copilot</h1>
        <Link
          href="/repos/new"
          className="inline-flex items-center gap-1 rounded-md border border-[var(--border-subtle)] px-2 py-1 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
        >
          <Plus size={14} /> Add
        </Link>
      </div>

      <nav className="space-y-1">
        <Link
          href="/repos"
          className={clsx(
            "block rounded-md px-2 py-1.5 text-sm",
            pathname === "/repos" ? "bg-[var(--bg-elevated)] text-[var(--text-primary)]" : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
          )}
        >
          Repositories
        </Link>
      </nav>

      <div className="mt-4 border-t border-[var(--border-subtle)] pt-3">
        <p className="mb-2 text-xs uppercase tracking-wide text-[var(--text-secondary)]">Your repos</p>
        {isLoading ? <p className="text-xs text-[var(--text-secondary)]">Loading...</p> : null}
        <div className="space-y-1">
          {repos?.map((repo) => (
            <Link
              key={repo.id}
              href={`/repos/${repo.id}`}
              className={clsx(
                "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm",
                pathname?.startsWith(`/repos/${repo.id}`)
                  ? "bg-[var(--bg-elevated)] text-[var(--text-primary)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]",
              )}
            >
              <StatusDot status={repo.status} />
              <span className="truncate">{repo.name}</span>
            </Link>
          ))}
        </div>
      </div>
    </aside>
  );
}

