"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { withApi } from "@/components/providers/auth-provider";

interface HealthResponse {
  status: string;
  llm_provider?: string;
}

export function Topbar() {
  const { user, signOut, authedFetch } = useAuth();
  const [health, setHealth] = useState<HealthResponse | null>(null);

  useEffect(() => {
    let cancelled = false;

    authedFetch(withApi("/api/health"))
      .then((res) => res.json())
      .then((data: HealthResponse) => {
        if (!cancelled) {
          setHealth(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setHealth(null);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [authedFetch]);

  return (
    <header className="flex h-12 items-center justify-between border-b border-[var(--border-subtle)] bg-[var(--bg-secondary)] px-4">
      <div className="text-xs text-[var(--text-secondary)]">
        {health?.status === "ok" ? `API healthy${health.llm_provider ? ` (${health.llm_provider})` : ""}` : "API status unknown"}
      </div>
      <div className="flex items-center gap-3 text-xs">
        <span className="text-[var(--text-secondary)]">{user?.email}</span>
        <button
          type="button"
          onClick={() => void signOut()}
          className="rounded-md border border-[var(--border-subtle)] px-2 py-1 text-[var(--text-primary)]"
        >
          Sign out
        </button>
      </div>
    </header>
  );
}

